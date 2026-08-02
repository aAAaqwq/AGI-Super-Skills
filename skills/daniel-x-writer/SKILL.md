---
name: daniel-x-writer
description: "Use for concise Chinese X/Twitter posts in Daniel's first-person voice, mixing human tension, numerical evidence, explicit decision rules, and a sharp reflective ending."
metadata: {"runtime_effects":"local-read-only; does not publish or call network services"}
---

# Daniel X Writer

Turn raw analysis into one copy-ready X post that sounds lived-in, not generated.

## Draft workflow

1. Identify the one thing the reader should remember. Drop secondary analysis.
2. Open with a real human impulse, doubt, mistake, or tension. Prefer “我当时想……” over a generic market summary.
3. Personify the Agent once as a calm counterforce: it may press a hand down, ask one hard question, or refuse to validate a hunch. Do not turn it into a cute mascot or an oracle.
4. Keep at most three hard observations. Preserve the strongest prices, volumes, ratios, or measured facts exactly.
5. Convert the decision into a rule: state the trigger and, when relevant, the condition that proves the idea wrong.
6. End with a short human insight. Make the point about discipline, thinking, or responsibility—not about being right.
7. Compress and verify before responding.

## Voice rules

- Sound direct, self-aware, and slightly sharp.
- Mix emotion with evidence; never replace evidence with drama.
- Use short sentences and 3–5 visual paragraphs.
- Use no more than one metaphor and one quoted Agent line.
- Prefer concrete verbs: `按住`, `逼我写清`, `砸出`, `认错`.
- Let numbers carry credibility. Do not explain every indicator.
- Keep the Agent subordinate to human responsibility: it challenges the decision; it does not own the trade.

Read [references/style-examples.md](references/style-examples.md) when matching tone, selecting a structure, or diagnosing why a draft feels generic.

## X length contract

- Default to one ordinary X post unless the user explicitly asks for a thread or long post.
- Treat 280 weighted characters as the hard ceiling. Target 240–260 to leave editing room.
- Never solve an over-limit draft by silently turning it into a thread.
- Remove headings, repeated caveats, full evidence chains, and decorative adjectives before removing decisive facts.
- When a draft is stored in a local UTF-8 text file, run:

```bash
python3 scripts/check_x_length.py /absolute/path/to/draft.txt
```

The checker deliberately overcounts non-ASCII characters and URLs conservatively. If it reports `over`, shorten the post and rerun it. Treat the final X composer as authoritative when available.

Run its local regression tests after changing the checker:

```bash
python3 -m unittest scripts/test_check_x_length.py
```

## Truth and risk rules

- Separate what happened before the decision from what happened afterward.
- Never turn a subjective scenario weight into a model probability or win rate.
- Never invent entry price, position size, leverage, profit, backtest results, or data provenance.
- For financial content, use a brief historical-recap boundary when readers could mistake the post for a live signal. Do not bury the post under legal boilerplate.
- Prefer “提高可信度” to “证明”，and “偏空依据” to “必跌信号”.
- If the source is internally inconsistent, preserve the core story but flag the conflict instead of repairing facts silently.

## Output contract

- Return exactly one copyable text block by default.
- Do not add analysis, character-count commentary, alternative versions, hashtags, or a publishing plan unless requested.
- Keep the user's language and natural code-switching. Use `Agent`, `BB`, prices, and ticker notation only where they feel native.
- Before returning, check: human tension, one Agent moment, no more than three facts, trigger, invalidation when available, sharp ending, and length under the requested limit.
