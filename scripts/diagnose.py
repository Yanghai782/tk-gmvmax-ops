#!/usr/bin/env python3
"""GMV Max creative data diagnosis tool.

Reads a TikTok GMV Max creative data export (.xlsx or .csv) and produces
a diagnostic report. Auto-detects column names and currency/country.
Works with any GMV Max export format.
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re, json
import sys, io

# Fix stdout for Chinese Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Country detection by currency -> fee mapping
# Total fee = platform commission (non-Mall default) + transaction fee
CURRENCY_COUNTRY = {
    "USD": "VN",  # Vietnam uses USD in cross-border
    "VND": "VN",
    "THB": "TH",
    "MYR": "MY",
    "SGD": "SG",
    "PHP": "PH",
    "IDR": "ID",
}
COUNTRY_FEES = {
    "VN": 0.160, "TH": 0.112, "MY": 0.158,
    "SG": 0.083, "PH": 0.072, "ID": 0.090,
}
COUNTRY_NAMES = {
    "VN": "Vietnam", "TH": "Thailand", "MY": "Malaysia",
    "SG": "Singapore", "PH": "Philippines", "ID": "Indonesia",
}


def detect_country(df):
    """Detect country from currency column."""
    for col in df.columns:
        if "currency" in str(col).lower() or "货币" in str(col) or "幣" in str(col):
            vals = df[col].dropna().unique()
            for v in vals:
                v = str(v).strip().upper()
                if v in CURRENCY_COUNTRY:
                    return CURRENCY_COUNTRY[v], v
    return "VN", "USD"  # default


def map_columns(df):
    """Auto-detect column names from Chinese/English headers."""
    col_map = {}
    keywords = {
        "cost": ["成本", "花费", "cost", "spend", "消耗"],
        "orders": ["订单", "訂單", "orders", "sku", "order"],
        "cpa": ["下单成本", "cpa", "cost per", "平均下单"],
        "roi": ["roi", "ROI", "投产"],
        "revenue": ["收入", "总收入", "revenue", "gmv", "销售额"],
        "impressions": ["曝光", "展示", "impression", "展现"],
        "clicks": ["点击", "click", "點擊"],
        "ctr": ["点击率", "ctr", "click through", "點擊率"],
        "cvr": ["转化率", "cvr", "conversion", "轉化率"],
        "status": ["状态", "狀態", "status"],
        "publish_time": ["发布", "發布", "publish", "time", "时间", "時間"],
        "creative": ["素材", "creative", "创意", "創意"],
        "account": ["账号", "帳號", "account", "tiktok"],
        "currency_col": ["货币", "currency", "幣"],
    }
    for key, kws in keywords.items():
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in kws):
                col_map[key] = col
                break
        if key not in col_map:
            col_map[key] = None
    return col_map


def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def safe_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def load_data(path):
    if path.endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)


def diagnose(df, target_roi=None, target_cpa=None, cpm_cap=None, country="VN", product_cost=None, shipping=0):
    now = datetime.now()
    cm = map_columns(df)
    fee_rate = COUNTRY_FEES.get(country, 0.10)

    # Build working data
    cost_col = cm["cost"]
    orders_col = cm["orders"]
    roi_col = cm["roi"]
    rev_col = cm["revenue"]
    imp_col = cm["impressions"]
    ctr_col = cm["ctr"]
    cvr_col = cm["cvr"]
    cpa_col = cm["cpa"]
    status_col = cm["status"]
    time_col = cm["publish_time"]

    # Filter active
    mask = pd.Series(True, index=df.index)
    if cost_col:
        mask &= df[cost_col].apply(safe_float) > 0
    active = df[mask].copy()
    has_orders = active[active[orders_col].apply(safe_int) > 0] if orders_col else active

    # Aggregate metrics
    total_cost = active[cost_col].apply(safe_float).sum() if cost_col else 0
    total_orders = active[orders_col].apply(safe_int).sum() if orders_col else 0
    total_revenue = active[rev_col].apply(safe_float).sum() if rev_col else 0
    overall_roi = total_revenue / total_cost if total_cost > 0 else 0
    avg_price = total_revenue / total_orders if total_orders > 0 else 0

    avg_ctr = has_orders[ctr_col].apply(safe_float).mean() if ctr_col and len(has_orders) > 0 else 0
    avg_cvr = has_orders[cvr_col].apply(safe_float).mean() if cvr_col and len(has_orders) > 0 else 0
    avg_cpa = total_cost / total_orders if total_orders > 0 else 999

    # Auto-calculate CPM cap if not provided
    if cpm_cap is None and avg_ctr > 0 and avg_cvr > 0 and avg_price > 0:
        gpm_auto = avg_price * avg_ctr * avg_cvr * 1000
        auto_target_roi = target_roi if target_roi else (overall_roi * 0.8 if overall_roi > 1 else 2.0)
        cpm_cap = gpm_auto / auto_target_roi

    # Auto-calculate target CPA if not provided
    if target_cpa is None and avg_price > 0:
        target_cpa = avg_cpa * 1.2 if avg_cpa < 999 else avg_price / 3

    # Break-even ROI — requires product cost
    be_roi = None
    if product_cost is not None and avg_price > 0:
        total_cost_per_order = product_cost + shipping + avg_price * fee_rate
        if total_cost_per_order < avg_price:
            be_roi = avg_price / (avg_price - total_cost_per_order)

    # Diagnostic flags
    flags = {
        "zero_conv": [],
        "cpm_high": [],
        "cpa_high": [],
        "roi_low": [],
        "learning": [],
        "decay_risk": [],
        "winners": [],
    }

    for idx, row in active.iterrows():
        cost = safe_float(row[cost_col]) if cost_col else 0
        orders = safe_int(row[orders_col]) if orders_col else 0
        roi = safe_float(row[roi_col]) if roi_col else 0
        cpa = safe_float(row[cpa_col]) if cpa_col else 999

        # CPM from cost/impressions
        imp = safe_int(row[imp_col]) if imp_col else 0
        cpm = (cost / imp * 1000) if imp > 0 and cost > 0 else 0

        # Days since publish
        days = None
        if time_col and pd.notna(row.get(time_col)):
            try:
                pub = pd.to_datetime(row[time_col])
                days = (now - pub).days
            except:
                pass

        # Flags
        if orders == 0 and days is not None and days >= 3 and cost > 0:
            flags["zero_conv"].append((idx, cost, row.get(cm["creative"], "") if cm["creative"] else ""))

        if cpm_cap and cpm > cpm_cap and cost > 5:
            flags["cpm_high"].append((idx, cpm, row.get(cm["creative"], "") if cm["creative"] else ""))

        if target_cpa and cpa > target_cpa * 1.5 and orders >= 3:
            flags["cpa_high"].append((idx, cpa, row.get(cm["creative"], "") if cm["creative"] else ""))

        if target_roi and roi > 0 and roi < target_roi * 0.7 and cost > 10:
            flags["roi_low"].append((idx, roi, row.get(cm["creative"], "") if cm["creative"] else ""))

        if 0 < orders < 50 and cost > 0:
            flags["learning"].append(idx)

        if days is not None and 14 <= days <= 28 and cost > 10:
            flags["decay_risk"].append(idx)

        if roi > 3 and orders >= 5:
            flags["winners"].append((idx, roi, orders, cpa, row.get(cm["creative"], "") if cm["creative"] else ""))

    # Status breakdown
    status_counts = df[status_col].value_counts() if status_col else pd.Series()

    # Column mapping info
    col_info = {k: v for k, v in cm.items() if v is not None}

    return {
        "total_creatives": len(df),
        "active_creatives": len(active),
        "total_cost": total_cost,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "overall_roi": overall_roi,
        "avg_price": avg_price,
        "avg_ctr": avg_ctr,
        "avg_cvr": avg_cvr,
        "avg_cpa": avg_cpa,
        "country": country,
        "fee_rate": fee_rate,
        "be_roi": be_roi,
        "cpm_cap": cpm_cap,
        "target_cpa": target_cpa,
        "status_counts": status_counts,
        "flags": flags,
        "df": df,
        "active": active,
        "col_info": col_info,
    }


def print_report(r):
    cname = COUNTRY_NAMES.get(r["country"], r["country"])
    print("=" * 65)
    print(f"  GMV Max Creative Diagnosis  |  {cname}")
    print("=" * 65)
    print(f"  Total Creatives:        {r['total_creatives']}")
    print(f"  Active (spend > 0):     {r['active_creatives']}")
    print()
    print(f"  Total Spend:            ${r['total_cost']:,.2f}")
    print(f"  Total Orders:           {r['total_orders']}")
    print(f"  Total Revenue:          ${r['total_revenue']:,.2f}")
    print(f"  Overall ROI:            {r['overall_roi']:.2f}")
    print(f"  Avg Order Value:        ${r['avg_price']:.2f}")
    print(f"  Avg CPA:                ${r['avg_cpa']:.2f}")
    print(f"  Avg CTR:                {r['avg_ctr']*100:.2f}%")
    print(f"  Avg CVR:                {r['avg_cvr']*100:.2f}%")
    print()

    # Thresholds
    fee_rate = r["fee_rate"]
    print(f"  Country Fee Rate:       {fee_rate*100:.1f}%")
    if r["be_roi"] is not None:
        be_str = f"{r['be_roi']:.2f}" if r['be_roi'] != float("inf") else "INF (unprofitable)"
        print(f"  Break-Even ROI:         {be_str}")
    if r.get("be_roi") is not None and r["be_roi"] != float("inf") and r["avg_price"] > 0:
        print(f"  Break-Even CPA:         ${r['avg_price']/r['be_roi']:.2f}")
    if r["cpm_cap"] is not None:
        print(f"  CPM Cap (est):          ${r['cpm_cap']:.2f}")
    print()

    # Status breakdown
    if len(r["status_counts"]) > 0:
        print("--- Status Breakdown ---")
        for status, count in r["status_counts"].items():
            print(f"  {status}: {count}")
        print()

    flags = r["flags"]

    if flags["winners"]:
        print(f"[WINNERS] {len(flags['winners'])} top creatives (ROI>3, 5+ orders):")
        for _, roi_val, orders, cpa_val, creative in sorted(flags["winners"], key=lambda x: -x[1])[:5]:
            c = str(creative)[:55]
            print(f"  ROI={roi_val:.1f}  Orders={orders}  CPA=${cpa_val:.2f}  |  {c}")
        print()

    if flags["zero_conv"]:
        print(f"[KILL] {len(flags['zero_conv'])} creatives: 3+ days, 0 conversions:")
        for _, cost_val, creative in flags["zero_conv"][:5]:
            c = str(creative)[:55]
            print(f"  Spend=${cost_val:.2f}  |  {c}")
        print()

    if flags["cpm_high"]:
        print(f"[CPM HIGH] {len(flags['cpm_high'])} creatives above CPM cap:")
        for _, cpm_val, creative in sorted(flags["cpm_high"], key=lambda x: -x[1])[:5]:
            c = str(creative)[:55]
            print(f"  CPM=${cpm_val:.2f}  |  {c}")
        print()

    if flags["cpa_high"]:
        print(f"[CPA HIGH] {len(flags['cpa_high'])} creatives above 1.5x target:")
        for _, cpa_val, creative in sorted(flags["cpa_high"], key=lambda x: -x[1])[:5]:
            c = str(creative)[:55]
            print(f"  CPA=${cpa_val:.2f}  |  {c}")
        print()

    if flags["roi_low"]:
        print(f"[ROI LOW] {len(flags['roi_low'])} creatives below 70% target:")
        for _, roi_val, creative in sorted(flags["roi_low"], key=lambda x: x[1])[:5]:
            c = str(creative)[:55]
            print(f"  ROI={roi_val:.2f}  |  {c}")
        print()

    if flags["learning"]:
        print(f"[LEARNING] {len(flags['learning'])} creatives in learning (<50 conversions)")
        print("  Do NOT touch these. Let the system learn.")
        print()

    if flags["decay_risk"]:
        print(f"[DECAY RISK] {len(flags['decay_risk'])} creatives in 14-28 day window")
        print("  Prepare fresh creatives before decay hits.")
        print()

    print("--- Recommendations ---")
    recs = []
    if flags["zero_conv"]:
        recs.append(f"Kill {len(flags['zero_conv'])} zero-conversion creatives (3+ days)")
    if flags["cpm_high"]:
        recs.append(f"Review {len(flags['cpm_high'])} creatives above CPM cap")
    if flags["roi_low"]:
        recs.append(f"Monitor {len(flags['roi_low'])} creatives with low ROI")
    if flags["winners"]:
        recs.append(f"Scale: iterate on {len(flags['winners'])} top-performing creatives")
    if flags["decay_risk"]:
        recs.append(f"Line up fresh creatives for {len(flags['decay_risk'])} aging assets")
    if flags["learning"]:
        recs.append(f"Protect {len(flags['learning'])} learning creatives: no pause/restart")
    if not recs:
        recs.append("Account looks healthy. Maintain daily creative pipeline.")
    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")

    # Quick calculator section if product cost was provided
    if r["be_roi"] is not None:
        print()
        print("--- Quick CPM Reference ---")
        print(f"  Break-Even ROI: {r['be_roi']:.2f}")
        for mult in [1.3, 1.5, 2.0]:
            troi = r["be_roi"] * mult
            gpm = r["avg_price"] * r["avg_ctr"] * r["avg_cvr"] * 1000
            cap = gpm / troi if troi > 0 else 999
            print(f"  At {mult}x BE (ROI={troi:.1f}): CPM cap=${cap:.2f}, CPA target=${r['avg_price']/troi:.2f}")
        daily = (r["avg_price"] / (r["be_roi"] * 1.3)) * 50 if r["be_roi"] > 0 else 0
        print(f"  Suggested daily budget: ${daily:.2f}")

    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="GMV Max creative diagnosis")
    parser.add_argument("path", help="Path to creative data export (.xlsx or .csv)")
    parser.add_argument("--target-roi", type=float, default=None, help="Target ROI (default: auto from data)")
    parser.add_argument("--target-cpa", type=float, default=None, help="Target CPA ($)")
    parser.add_argument("--cpm-cap", type=float, default=None, help="CPM cap ($, default: auto-calculated)")
    parser.add_argument("--product-cost", type=float, default=None, help="Product cost per unit ($, for break-even ROI)")
    parser.add_argument("--shipping", type=float, default=0, help="Shipping cost per order ($)")
    parser.add_argument("--country", type=str, default=None, choices=list(COUNTRY_FEES.keys()), help="Country code (auto-detect if omitted)")
    parser.add_argument("--fee-override", type=float, default=None, help="Override total fee rate (decimal)")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    args = parser.parse_args()

    df = load_data(args.path)
    country, currency = detect_country(df)
    if args.country:
        country = args.country
    if args.fee_override:
        COUNTRY_FEES[country] = args.fee_override

    r = diagnose(df, args.target_roi, args.target_cpa, args.cpm_cap, country, args.product_cost, args.shipping)
    r["detected_currency"] = currency

    if args.output:
        old = sys.stdout
        with open(args.output, "w", encoding="utf-8") as f:
            sys.stdout = f
            print_report(r)
            sys.stdout = old
        print(f"Report written to {args.output}")
    else:
        print_report(r)


if __name__ == "__main__":
    main()
