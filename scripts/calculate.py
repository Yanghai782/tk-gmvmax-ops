#!/usr/bin/env python3
"""TK GMV Max CPM threshold and break-even ROI calculator.

Uses official TikTok Shop commission + transaction fee rates per country.
Rates sourced from TikTok Shop Seller University, accessed 2026-06-27.
"""

import argparse
import sys

# Total fee rate = platform commission (non-Mall default) + transaction fee
# Actual rates vary by product category; these are the default rates.
# Use --fee-override to specify your exact category rate.
COUNTRY_FEES = {
    "VN": 0.160,  # Vietnam: 14.0% commission (non-Mall default) + ~2.0% tx fee
    "TH": 0.112,  # Thailand: ~8.0% commission (non-Mall mid-range) + 3.21% tx fee
    "MY": 0.158,  # Malaysia: ~12.0% commission (non-Mall mid-range) + 3.78% tx fee
    "SG": 0.083,  # Singapore: ~5.0% commission (non-Mall mid-range) + 3.27% tx fee
    "PH": 0.072,  # Philippines: ~5.0% commission (non-Mall mid-range) + 2.24% tx fee
    "ID": 0.090,  # Indonesia: estimated (not fetched from official source)
}


def calc_gpm(price, ctr, cvr):
    return price * ctr * cvr * 1000


def calc_cpm_cap(gpm, target_roi):
    return gpm / target_roi


def calc_breakeven_roi(price, cost, fee_rate, shipping=0):
    total_cost = cost + shipping + price * fee_rate
    if total_cost >= price:
        return float("inf")
    return price / (price - total_cost)


def calc_budget(target_cpa):
    return target_cpa * 50


def main():
    parser = argparse.ArgumentParser(description="TK GMV Max Calculator")
    parser.add_argument("--price", type=float, required=True, help="Average order value")
    parser.add_argument("--cost", type=float, required=True, help="Product cost per unit")
    parser.add_argument("--country", type=str, default="VN", choices=list(COUNTRY_FEES.keys()), help="TK Shop country")
    parser.add_argument("--ctr", type=float, required=True, help="CTR (e.g. 0.04)")
    parser.add_argument("--cvr", type=float, required=True, help="CVR (e.g. 0.05)")
    parser.add_argument("--target-roi", type=float, default=None, help="Target ROI")
    parser.add_argument("--target-cpa", type=float, default=None, help="Target CPA")
    parser.add_argument("--shipping", type=float, default=0, help="Shipping per order")
    parser.add_argument("--fee-override", type=float, default=None, help="Override total fee rate (e.g. 0.16 for 16%%)")

    args = parser.parse_args()
    fee_rate = args.fee_override if args.fee_override is not None else COUNTRY_FEES[args.country]

    gpm = calc_gpm(args.price, args.ctr, args.cvr)
    be_roi = calc_breakeven_roi(args.price, args.cost, fee_rate, args.shipping)
    target_roi = args.target_roi if args.target_roi is not None else (be_roi * 1.3 if be_roi != float("inf") else 2.0)
    cpm_cap = calc_cpm_cap(gpm, target_roi)
    target_cpa = args.target_cpa if args.target_cpa is not None else (args.price / target_roi if target_roi > 0 else args.price)
    budget = calc_budget(target_cpa)
    total_cost_order = args.cost + args.shipping + args.price * fee_rate
    net_margin = args.price - total_cost_order

    print("=" * 55)
    print("  TK GMV Max - Calculator Results")
    print("=" * 55)
    print(f"  Country:            {args.country} (total fee: {fee_rate*100:.1f}%)")
    print(f"  Selling Price:      ${args.price:.2f}")
    print(f"  Product Cost:       ${args.cost:.2f}")
    print(f"  Shipping:           ${args.shipping:.2f}")
    print(f"  Total Cost/Order:   ${total_cost_order:.2f}")
    print(f"  Net Margin/Order:   ${net_margin:.2f}")
    print()
    print(f"  CTR:                {args.ctr*100:.2f}%")
    print(f"  CVR:                {args.cvr*100:.2f}%")
    print()
    print("  --- Results ---")
    print(f"  GPM:                ${gpm:.2f}  (per 1000 impressions)")
    print(f"  Break-Even ROI:     {be_roi:.2f}")
    print(f"  Target ROI:         {target_roi:.2f}")
    print(f"  CPM Cap:            ${cpm_cap:.2f}  (max at target ROI)")
    print(f"  Target CPA:         ${target_cpa:.2f}")
    print(f"  Daily Budget:       ${budget:.2f}  (50 conversions)")
    print("=" * 55)

    if cpm_cap < 1:
        print()
        print("  [!] WARNING: CPM cap below $1. GPM is very low.")
    if be_roi == float("inf"):
        print()
        print("  [!] CRITICAL: Product loses money at any ROI.")


if __name__ == "__main__":
    main()
