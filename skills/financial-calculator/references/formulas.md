# Financial Formulas Reference

## Future Value (FV)

Calculate the future value of an investment with compound interest.

**Formula:**
```
FV = PV × (1 + r/n)^(n×t)
```

Where:
- `FV` = Future Value
- `PV` = Present Value (initial investment)
- `r` = Annual interest rate (as decimal)
- `n` = Number of times interest is compounded per year
- `t` = Number of years

**Example:**
```
Initial investment: $10,000
Annual rate: 5% (0.05)
Time: 10 years
Compounding: Monthly (12)

FV = 10,000 × (1 + 0.05/12)^(12×10)
FV = 10,000 × (1.004167)^120
FV = $16,470.09
```

## Present Value (PV)

Calculate the present value (what a future amount is worth today).

**Formula:**
```
PV = FV / (1 + r/n)^(n×t)
```

Where:
- `PV` = Present Value
- `FV` = Future Value
- `r` = Annual discount rate (as decimal)
- `n` = Compounding frequency per year
- `t` = Number of years

**Example:**
```
Future value: $20,000
Discount rate: 5% (0.05)
Time: 10 years
Compounding: Monthly (12)

PV = 20,000 / (1 + 0.05/12)^(12×10)
PV = 20,000 / 1.6470
PV = $12,139.13
```

## Discount Calculation

Calculate final price after applying a percentage discount.

**Formula:**
```
Discount Amount = Original Price × (Discount % / 100)
Final Price = Original Price - Discount Amount
```

**Example:**
```
Original Price: $100
Discount: 20%

Discount Amount = 100 × 0.20 = $20
Final Price = 100 - 20 = $80
```

## Markup Calculation

Calculate selling price from cost and markup percentage.

**Formula:**
```
Markup Amount = Cost × (Markup % / 100)
Selling Price = Cost + Markup Amount
Profit Margin = (Markup Amount / Selling Price) × 100
```

**Example:**
```
Cost: $100
Markup: 30%

Markup Amount = 100 × 0.30 = $30
Selling Price = 100 + 30 = $130
Profit Margin = (30 / 130) × 100 = 23.08%
```

## Compound Interest

Calculate detailed compound interest breakdown.

**Formula:**
```
Final Amount = P × (1 + r/n)^(n×t)
Total Interest = Final Amount - P
Effective Annual Rate = (1 + r/n)^n - 1
```

Where:
- `P` = Principal (initial amount)
- `r` = Annual interest rate (as decimal)
- `n` = Compounding frequency
- `t` = Time in years

**Example:**
```
Principal: $10,000
Rate: 5% (0.05)
Time: 10 years
Compounding: Monthly (12)

Final Amount = 10,000 × (1 + 0.05/12)^(12×10) = $16,470.09
Total Interest = 16,470.09 - 10,000 = $6,470.09
Effective Rate = (1 + 0.05/12)^12 - 1 = 5.12%
```

## Annuity Future Value

Calculate future value of a series of equal payments.

**Formula:**
```
FV = PMT × [((1 + r)^n - 1) / r]
```

Where:
- `FV` = Future Value of annuity
- `PMT` = Payment amount per period
- `r` = Interest rate per period
- `n` = Number of periods

**Example:**
```
Monthly payment: $500
Annual rate: 6% (0.06)
Monthly rate: 0.06/12 = 0.005
Time: 5 years = 60 months

FV = 500 × [((1.005)^60 - 1) / 0.005]
FV = 500 × 69.77
FV = $34,885
```

## Annuity Present Value

Calculate present value of a series of equal future payments.

**Formula:**
```
PV = PMT × [(1 - (1 + r)^-n) / r]
```

Where:
- `PV` = Present Value of annuity
- `PMT` = Payment amount per period
- `r` = Interest rate per period
- `n` = Number of periods

**Example:**
```
Monthly payment: $1,000
Annual rate: 6% (0.06)
Monthly rate: 0.06/12 = 0.005
Time: 10 years = 120 months

PV = 1,000 × [(1 - (1.005)^-120) / 0.005]
PV = 1,000 × 90.07
PV = $90,073.45
```

## Compounding Frequencies

Common compounding frequencies:

| Frequency | Periods per Year (n) |
|-----------|---------------------|
| Annually | 1 |
| Semi-annually | 2 |
| Quarterly | 4 |
| Monthly | 12 |
| Weekly | 52 |
| Daily | 365 |
| Continuously | Use e^(rt) formula |

## Common Use Cases

### Investment Growth
Use **Future Value** to see how investments grow over time with compound interest.

### Loan Present Value
Use **Present Value** to determine what monthly payments are worth in today's dollars.

### Retail Discounts
Use **Discount Calculator** for sale prices and savings.

### Business Pricing
Use **Markup Calculator** to price products based on cost and desired profit margin.

### Savings Planning
Use **FV Tables** to compare different interest rates and time horizons.

### Retirement Planning
Use **Annuity** formulas for regular contributions or withdrawals.
