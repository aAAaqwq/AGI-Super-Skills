#!/usr/bin/env python3
"""
定价策略计算器 — 支持成本加成/价值定价/竞争定价/动态定价

Usage:
  python3 pricing_calc.py --model cost-plus --cost 50 --margin 40
  python3 pricing_calc.py --model value-based --value 200 --penetration 60
  python3 pricing_calc.py --model competitive --competitors "竞品A=99,竞品B=149,竞品C=199"
"""

import argparse, json

def cost_plus(cost: float, margin: float) -> dict:
    price = cost * (1 + margin / 100)
    return {"model": "成本加成", "cost": cost, "margin_pct": margin, "price": round(price, 2), "profit": round(price - cost, 2)}

def value_based(value: float, penetration: float = 60) -> dict:
    price = value * penetration / 100
    return {"model": "价值定价", "customer_value": value, "penetration_pct": penetration, "price": round(price, 2)}

def competitive(competitors: dict, strategy: str = "parity") -> dict:
    prices = list(competitors.values())
    avg = sum(prices) / len(prices)
    if strategy == "premium":
        price = avg * 1.2
    elif strategy == "discount":
        price = avg * 0.8
    else:
        price = avg
    return {"model": "竞争定价", "strategy": strategy, "competitor_prices": competitors, "avg_competitor": round(avg, 2), "recommended_price": round(price, 2)}

def main():
    parser = argparse.ArgumentParser(description="定价策略计算器")
    parser.add_argument("--model", "-m", required=True, choices=["cost-plus", "value-based", "competitive"])
    parser.add_argument("--cost", type=float, help="成本")
    parser.add_argument("--margin", type=float, default=40, help="target margin")
    parser.add_argument("--value", type=float, help="客户感知价值")
    parser.add_argument("--penetration", type=float, default=60, help="value penetration")
    parser.add_argument("--competitors", help='竞品价格，如"竞品A=99,竞品B=149"')
    parser.add_argument("--strategy", choices=["premium", "parity", "discount"], default="parity")
    parser.add_argument("--output", "-o", choices=["json", "table"], default="table")
    args = parser.parse_args()

    if args.model == "cost-plus":
        if not args.cost: return parser.print_help()
        r = cost_plus(args.cost, args.margin)
    elif args.model == "value-based":
        if not args.value: return parser.print_help()
        r = value_based(args.value, args.penetration)
    elif args.model == "competitive":
        if not args.competitors: return parser.print_help()
        comps = {}
        for p in args.competitors.replace("，", ",").split(","):
            k, v = p.split("=")
            comps[k.strip()] = float(v.strip())
        r = competitive(comps, args.strategy)

    if args.output == "json":
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for k, v in r.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for k2, v2 in v.items():
                    print(f"    {k2}: {v2}")
            else:
                print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
