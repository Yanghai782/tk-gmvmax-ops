# Core Formulas

## Formula Reference

### 1. GPM (Gross Profit per Mille)

`
GPM = Price * CTR * CVR * 1000
`

Revenue generated per 1,000 impressions. This is a product-level metric — it measures
how much money the product makes when shown 1,000 times, independent of ad cost.

- Price = average order value (AOV)
- CTR = click-through rate (e.g., 0.04 = 4%)
- CVR = conversion rate (e.g., 0.05 = 5%)

### 2. CPM Cap (Maximum Acceptable CPM)

`
CPM_cap = GPM / Target_ROI
`

The highest CPM a creative can have and still hit your target ROI.
If actual CPM > CPM_cap, the creative is losing money — kill it.

**Example:**
- Price = .50, CTR = 4.2%, CVR = 5.4%, Target ROI = 2.5
- GPM = 6.50 * 0.042 * 0.054 * 1000 = .74
- CPM_cap = 14.74 / 2.5 = .90

Any creative with CPM > .90 is below your 2.5 ROI target.

### 3. Break-Even ROI

`
BreakEven_ROI = Price / (Price - Cost_per_Order)
`

Where:
`
Cost_per_Order = Product_Cost + Shipping + Price * Fee_Rate
`

**Example:**
- Price = , Cost = , Fee_Rate = 8%
- Cost_per_Order = 4 + 10*0.08 = .80
- BreakEven_ROI = 10 / 4.80 = 2.08

ROI must exceed 2.08 to be profitable.

### 4. ECPM (Effective Cost Per Mille)

`
ECPM = CTR * CVR * Price * Platform_Weight
`

The platform's internal scoring of a creative. Higher ECPM = more budget allocation from GMV Max.
System favors creatives with high click-through and conversion rates regardless of ROI setting.

### 5. Budget Formula

`
Daily_Budget = Target_CPA * 50
`

Ensures ~50 conversions per day for the system to exit learning phase.
Never set budget below this minimum during cold start.

### 6. Starting Bid for New Campaigns

`
Starting_Bid = Target_CPA * 1.2 ~ 1.5
`

Give the system room to explore. Narrow later once CPA stabilizes.

## Usage Priority

1. Always calculate **BreakEven_ROI** first — know your floor
2. Calculate **GPM** from actual or estimated CTR/CVR
3. Derive **CPM_cap** from your target ROI
4. Use CPM_cap as your creative kill switch
