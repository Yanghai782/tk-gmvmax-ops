---
name: tk-gmvmax-ops
description: 'TikTok Shop GMV Max advertising operations toolkit. Use when analyzing GMV Max ad performance data (creative-level or product-level), diagnosing creatives, calculating CPM thresholds and break-even ROI, planning cold starts, or troubleshooting delivery issues. Supports multi-country fee configs (VN, TH, MY, SG, PH, ID). Triggered by GMV Max data exports (.xlsx .csv), questions about cold start strategy, CPM ROI formula calculations, creative performance diagnosis, product profitability analysis, or daily ad account operations.'
---

# TK GMV Max Operations Toolkit

## Data Type Detection (Automatic)

File is loaded by `diagnose.py` and analyzed. The script auto-detects:

| Columns Present | Data Type | Script Action |
|----------------|-----------|---------------|
| CTR, CVR, impressions, clicks, creative name, status | Creative-level | Full creative diagnosis |
| Product ID, SKU orders, revenue, cost, ROI (NO impressions/CTR/CVR) | Product-level | Product financial analysis with scenario table |

**No manual inspection needed** — `diagnose.py` detects and routes automatically.

## One-Stop Diagnosis (Both Data Types)

User provides any GMV Max data export (.xlsx or .csv). Everything auto-detected.

**Only ask the user for:** product cost per unit (not in ad data).

Then run:

```
python scripts/diagnose.py <file> --product-cost N
```

Output includes ALL of:
- Creative diagnosis: winners, kill list, CPM/ROI flags, learning phase status
- Break-even ROI & CPA
- CPM cap (auto-calculated)
- Quick CPM reference at 1.3x/1.5x/2.0x break-even
- Suggested daily budget
- Actionable recommendations

Without `--product-cost`: skips break-even/Budget, still outputs CPM cap and full diagnosis.

## Product-Level Analysis Manual Reference

`diagnose.py` handles product-level data automatically. However, when Python is unavailable, use `references/product-analysis.md` for manual computation workflow. Key steps:

1. Read the file (PowerShell COM on Windows, or CSV reader)
2. Ask user for product cost. If unknown, show break-even scenario table.
3. Compute all formulas from `references/formulas.md` by hand.

## No-Python Fallback

If `python` and `python3` are both unavailable:
- Read Excel via PowerShell COM: `New-Object -ComObject Excel.Application`
- Or read CSV directly with file tools
- Compute all formulas from `references/formulas.md` and `references/product-analysis.md` by hand
- Present results in the same structured format as the scripts would

Do NOT abort. Every formula is basic arithmetic.

## Cold Start Planning

Load `references/cold-start.md`. Ask user for: product info, country, target CPA (if known).

## Self-Service: Calculator (standalone)

```
python scripts/calculate.py --price X --cost Y --country VN --ctr 0.04 --cvr 0.05
```

## What the Skill Knows vs What It Asks

| Auto-Detected | Must Ask User |
|--------------|---------------|
| Country, currency, fee rate (from Excel) | **Product cost** (always) |
| CTR, CVR, AOV, CPA, ROI (from Excel) | Target ROI (optional, has default) |
| Column names (Chinese/English auto-map) | Shipping cost (optional) |
| CPM cap, break-even, budget (calculated) | — |
| Data type: creative vs product-level | — |

## Core Principles

- Broad to narrow audience. Never narrow during cold start.
- Creative quality drives ECPM. One winner carries a product.
- Never pause/restart during learning (< 50 conversions).
- 3 days, 0 conversions = kill.
- CPM > CPM cap = losing money.

## Resources

- `scripts/diagnose.py` — One-stop: creative diagnosis + break-even + CPM cap + budget
- `scripts/calculate.py` — Standalone CPM/ROI/GPM calculator
- `references/product-analysis.md` — Product-level aggregate data analysis workflow
- `references/country-fees.md` — Official rates by country (commission + tx fee)
- `references/formulas.md` — Full formula derivations
- `references/cold-start.md` — Day 1-3+ playbook
- `references/daily-checklist.md` — Daily ops + decision matrix
- `references/troubleshooting.md` — High CPM, flash spend, new campaign rules
- `references/a1-a5.md` — Audience funnel + creative strategy by stage
