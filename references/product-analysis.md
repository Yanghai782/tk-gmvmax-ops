# Product-Level Analysis (Aggregate Data)

Use when the user provides a product-summary export rather than creative-level data.
Auto-detect by checking if columns like impressions/CTR/CVR/clicks are missing, and SKU orders/revenue/ROI are present.

## Data Shape Recognition

| Type | Typical Columns | Analysis Available |
|------|----------------|-------------------|
| Creative-level | Impressions, clicks, CTR, CVR, cost, orders, ROI, creative name, status, publish time | Full diagnose.py output |
| Product-level | Product ID, product name, SKU orders, revenue, cost, ROI, currency | Product financial analysis (this guide) |

If the file is product-level, DO NOT run diagnose.py expecting creative flags. Use the manual workflow below (or let the updated diagnose.py auto-detect).

## Product Analysis Workflow

### Step 1: Extract Core Metrics

From the Excel/CSV:
- Total ad spend (cost)
- Total orders (SKU orders)
- Total revenue (revenue/gmv)
- ROI (directly or compute: revenue / cost)
- AOV = revenue / orders
- CPA = cost / orders

### Step 2: Detect Country & Fee Rate

From currency column -> map to country code:

| Currency | Country | Code | Fee Rate |
|----------|---------|------|----------|
| USD (cross-border) | Vietnam | VN | 16.0% |
| VND | Vietnam | VN | 16.0% |
| THB | Thailand | TH | 11.2% |
| MYR | Malaysia | MY | 15.8% |
| SGD | Singapore | SG | 8.3% |
| PHP | Philippines | PH | 7.2% |
| IDR | Indonesia | ID | 9.0% |

Fee rate = platform commission (non-Mall default) + transaction fee.
Use `--fee-override` if user specifies exact category rate.

### Step 3: Fee Impact Per Order

```
Fee_per_order = AOV * Fee_Rate
Revenue_after_fee = AOV - Fee_per_order
```

### Step 4: Break-Even Analysis

Ask user for product cost per unit. If they don't provide it, show a scenario table.

```
Total_cost_per_order = Product_Cost + Shipping + AOV * Fee_Rate
BreakEven_ROI = AOV / (AOV - Total_cost_per_order)
BreakEven_CPA = AOV / BreakEven_ROI
Max_Product_Cost = (AOV - AOV * Fee_Rate) - AOV / Current_ROI
```

If AOV - Total_cost_per_order <= 0: product loses money at any ROI — warn immediately.

### Step 5: Scenario Table (when product cost unknown)

Show break-even ROI at multiple product cost levels. Step size = max(0.5, round(AOV/10, 1)).
Mark which scenarios are profitable given current ROI.

### Step 6: Budget Suggestion

```
Daily_budget = CPA * 50
```

Ensure ~50 conversions/day to exit learning phase.

### Step 7: Recommendations

Based on findings:
- ROI > BE_ROI by 1.5x+: Healthy — consider scaling budget
- ROI > BE_ROI but < 1.3x: Thin margin — monitor closely
- ROI < BE_ROI: Unprofitable — raise price or cut product cost
- CPA very low relative to AOV: Good product-creative fit
- Orders > 50: Exited learning phase, stable
- For creative-level diagnosis: export full creative data from GMV Max

## Quick Calculator (Manual)

When Python is unavailable, compute by hand:

```
GPM = AOV * CTR * CVR * 1000
CPM_cap = GPM / Target_ROI
BE_ROI = AOV / (AOV - product_cost - shipping - AOV * fee_rate)
BE_CPA = AOV / BE_ROI
Daily_budget = Target_CPA * 50
```

## No-Python Fallback

If `python` or `python3` is not available:
1. Read the Excel via PowerShell COM (on Windows) or other means
2. Extract data manually
3. Compute all formulas in this guide manually
4. Present results in the same format as diagnose.py would

Do NOT abort with "Python not found." The formulas are simple and can be computed directly.
