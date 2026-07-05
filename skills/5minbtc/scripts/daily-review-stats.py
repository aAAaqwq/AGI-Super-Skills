#!/usr/bin/env python3
"""5minbtc daily review stats analyzer.

Reads 5minbtc-log.jsonl, filters to a single trading day, and computes the
per-dimension breakdown that the daily-review task needs (per-bias accuracy,
per-vol-band accuracy, MAE, max error, win streak, error-sign / systematic-bias
check). This is the structured analysis that `5minbtc-log.py stats` does NOT
provide (it only gives aggregate direction/range/MAE/max).

Built-in data-quality handling:
  * dedup by candle start (cron double-fire / manual+auto overlap -> keep last)
  * filter vol_pct > 200  (lesson 15: 0/near-0-denominator explosive glitch,
    NOT real volume)
  * error-sign analysis   (lesson 19: all-same-sign => engine fighting trend)

IMPORTANT UNIT CONVENTION
-------------------------
`error_pct` in the JSONL is ALREADY in percent units. -0.32 means -0.32%,
NOT -0.0032. Do NOT multiply by 100 a second time when computing MAE.

Field names are read defensively via alias lookup so the script survives small
changes to the log schema. Run on first use to confirm keys match.

Usage:
    python3 scripts/daily-review-stats.py            # today
    python3 scripts/daily-review-stats.py 2026-06-23 # specific date
"""
import json
import sys
import os
from collections import defaultdict

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   os.pardir, "5minbtc-log.jsonl")

VOL_GLITCH_THRESHOLD = 200.0  # lesson 15
SYSTEMATIC_BIAS_MIN_RUNS = 5  # lesson 19


def _get(r, *keys, default=None):
    """Return the first present, non-None key among aliases."""
    for k in keys:
        if k in r and r[k] is not None:
            return r[k]
    return default


def _is_settled(r):
    """A record is settled if it has an actual close price or an explicit flag."""
    if _get(r, "settled"):
        return True
    if _get(r, "actual_close", "actual", "actual_price", "close") is not None:
        return True
    return False


def load_day(log_path, day):
    recs = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            hay = " ".join(str(r.get(k, "")) for k in ("ts", "candle", "date"))
            if day in hay and _is_settled(r):
                recs.append(r)
    return recs


def dedup(records):
    """Same candle start twice => keep the last record."""
    by_candle = {}
    for r in records:
        key = _get(r, "candle", "candle_start", "iso", default=r.get("ts"))
        by_candle[key] = r
    return sorted(by_candle.values(),
                  key=lambda x: _get(x, "candle", "ts", default=""))


def vol_band(v):
    if v < 40:
        return "low(<40%)"
    if v < 80:
        return "mid(40-80%)"
    return "high(>80%)"


def pct(ok, n):
    return 100.0 * ok / n if n else 0.0


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else None
    if day is None:
        import datetime
        day = datetime.date.today().isoformat()

    if not os.path.exists(LOG):
        print("Log not found: %s" % LOG)
        return

    records = load_day(LOG, day)
    if not records:
        print("No settled records for %s" % day)
        print("If a full trading day was expected (30-40 rounds), this is a")
        print("cron coverage anomaly -> check provider balance / fallback chain")
        print("See references/cron-llm-provider-failure.md")
        return

    records = dedup(records)
    valid = [r for r in records
             if (_get(r, "vol_pct", "vol", default=0) or 0) <= VOL_GLITCH_THRESHOLD]
    glitch = [r for r in records
              if (_get(r, "vol_pct", "vol", default=0) or 0) > VOL_GLITCH_THRESHOLD]

    print("=== %s ===" % day)
    print("deduped=%d  valid=%d  vol_glitch_filtered=%d"
          % (len(records), len(valid), len(glitch)))
    for r in glitch:
        print("  VOL_GLITCH: %s vol_pct=%s"
              % (_get(r, "candle", "ts", default="?"),
                 _get(r, "vol_pct", "vol")))
    print()

    n = len(valid)
    if n == 0:
        print("No valid records after filtering.")
        return

    def dir_ok(r):
        return bool(_get(r, "direction_correct", "dir_correct", default=False))

    def rng_ok(r):
        return bool(_get(r, "in_range", "range_correct", default=False))

    dir_n = sum(1 for r in valid if dir_ok(r))
    rng_n = sum(1 for r in valid if rng_ok(r))
    errs = [abs(_get(r, "error_pct", "err_pct", default=0.0)) for r in valid]
    raw = [_get(r, "error_pct", "err_pct", default=0.0) for r in valid]
    mae = sum(errs) / n
    max_pos = max(raw)
    max_neg = min(raw)

    print("--- HEADLINE ---")
    print("Direction: %d/%d = %.1f%%" % (dir_n, n, pct(dir_n, n)))
    print("Range:     %d/%d = %.1f%%" % (rng_n, n, pct(rng_n, n)))
    print("MAE: %.3f%%   (error_pct is already in percent units)" % mae)
    print("Max err: +%.3f%% / %.3f%%" % (max_pos, max_neg))
    print()

    # bias breakdown
    print("--- BY BIAS ---")
    bg = defaultdict(list)
    for r in valid:
        bg[_get(r, "bias", default="?")].append(r)
    for b in ("bull", "bear", "neutral"):
        g = bg.get(b, [])
        if g:
            c = sum(1 for r in g if dir_ok(r))
            print("  %-7s %d/%d = %.1f%%" % (b, c, len(g), pct(c, len(g))))
    print()

    # vol breakdown
    print("--- BY VOLUME ---")
    vg = defaultdict(list)
    for r in valid:
        vg[vol_band(_get(r, "vol_pct", "vol", default=0) or 0)].append(r)
    for v in ("low(<40%)", "mid(40-80%)", "high(>80%)"):
        g = vg.get(v, [])
        if g:
            c = sum(1 for r in g if dir_ok(r))
            print("  %-13s %d/%d = %.1f%%" % (v, c, len(g), pct(c, len(g))))
    print()

    # streak
    best = cur = 0
    for r in valid:
        if dir_ok(r):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    print("Max win streak: %d" % best)

    # error-sign / systematic-bias (lesson 19)
    pos = sum(1 for e in raw if e > 0)
    neg = sum(1 for e in raw if e < 0)
    flag = ("SYSTEMATIC_BIAS (engine fighting trend -> lesson 19)"
            if (pos >= SYSTEMATIC_BIAS_MIN_RUNS or neg >= SYSTEMATIC_BIAS_MIN_RUNS)
            else "ok")
    print("Error signs: +%d / -%d  =>  %s" % (pos, neg, flag))

    # coverage warning
    if n < 10:
        print()
        print("WARN: only %d valid rounds. A healthy trading day has 30-40." % n)
        print("      Likely silent cron/provider failure -> check provider balance.")
    print()

    print("--- PER-ROUND (chronological) ---")
    for r in valid:
        dc = "OK" if dir_ok(r) else "X"
        rc = "OK" if rng_ok(r) else "X"
        ctime = str(_get(r, "candle", "ts", default=""))[11:16]
        print("%s | %-7s conf=%3s | pred=%s act=%s err=%+.3f%% | dir%s rng%s | vol=%s%%"
              % (ctime, _get(r, "bias", default="?"), _get(r, "confidence", default="?"),
                 _get(r, "pred_close", "pred", default="?"),
                 _get(r, "actual_close", "actual", default="?"),
                 _get(r, "error_pct", "err_pct", default=0.0),
                 dc, rc, _get(r, "vol_pct", "vol", default="?")))


if __name__ == "__main__":
    main()
