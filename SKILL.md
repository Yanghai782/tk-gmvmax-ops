---
name: tk-gmvmax-ops
description: >-
  TikTok Shop GMV Max advertising operations toolkit. Use when analyzing
  GMV Max ad performance data, diagnosing creatives, calculating CPM
  thresholds break-even ROI, planning cold starts, or troubleshooting delivery
  issues. Supports multi-country fee configs (VN, TH, MY, SG, PH, ID).
  Triggered by GMV Max data exports (.xlsx), questions about cold start
  strategy, CPM ROI formula calculations, creative performance diagnosis,
  or daily ad account operations.
---

# TK GMV Max Operations Toolkit

## Quick Start

Three workflows. Each tells you exactly what to ask the user before running.

## Workflow 1: Diagnose Creatives (zero-config)

User provides a GMV Max creative data export (.xlsx or .csv). Everything else is auto-detected.

**No questions needed.** Run immediately:

```
python scripts/diagnose.py <path-to-file>
```

The script auto-detects: column names, country (from currency), fee rate, CPM cap.
Optional flags: `--target-roi N`, `--target-cpa N`, `--cpm-cap N`, `--country VN`.

## Workflow 2: Calculate CPM Thresholds

**MUST ask the user for these before running:**

1. Product selling price (per order, in local currency)
2. Product cost per unit
3. Country code (VN/TH/MY/SG/PH/ID)
4. Estimated CTR (e.g. 0.04 for 4%)
5. Estimated CVR (e.g. 0.05 for 5%)

Optional (has defaults): target ROI, target CPA, shipping cost, fee override.

If the user provides an ad data export first, extract CTR/CVR/price from it automatically with diagnose.py, then ask only for the missing product cost.

Run:
```
python scripts/calculate.py --price 10.00 --cost 4.00 --country VN --ctr 0.04 --cvr 0.05
```

## Workflow 3: Cold Start Planning

**MUST ask the user:**

1. Product info: what are they launching?
2. Country
3. Estimated target CPA (if known; otherwise derive from price/data)

Then load `references/cold-start.md` for the full playbook, and calculate budget + bid from the inputs.

## Important: When to Ask vs When to Auto-Detect

| Data Point | Source |
|-----------|--------|
| Price (AOV) | Auto from diagnose.py OR ask user |
| CTR, CVR | Auto from diagnose.py OR ask user |
| Country, Fee Rate | Auto from diagnose.py (currency column) |
| CPM Cap | Auto-calculated from above |
| **Product Cost** | **ALWAYS ask user** (not in ad data) |
| **Target ROI** | **Ask user** (business decision) |
| Target CPA | Auto-derived from price/ROI OR ask user |
| Shipping Cost | Ask user if not zero |

## Core Principles

- Broad to narrow audience strategy
- Creative quality drives ECPM; one winner carries a product
- Never pause/restart during learning phase (< 50 conversions)
- 3 days, 0 conversions = kill the creative
- CPM > CPM cap = losing money (use the formula)

## Resources

- `scripts/diagnose.py` -- Auto-detect creative diagnosis from any GMV Max export
- `scripts/calculate.py` -- CPM threshold, break-even ROI, GPM calculator
- `references/country-fees.md` -- Official commission + transaction fee rates by country
- `references/formulas.md` -- Full formula derivations with examples
- `references/cold-start.md` -- Day 1-3+ cold start playbook
- `references/daily-checklist.md` -- Daily operations checklist + decision matrix
- `references/troubleshooting.md` -- High CPM, flash spend, campaign creation decisions
- `references/a1-a5.md` -- A1-A5 audience funnel and creative strategy by stage
