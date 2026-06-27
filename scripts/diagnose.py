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
        "creative_id": ["作品", "creative id", "ID"],
        "creative": ["素材", "creative", "创意", "創意"],
        "account": ["账号", "帳號", "account", "tiktok"],
        "currency_col": ["货币", "currency", "幣"],
        "play_2s": ["2 秒", "2s"],
        "play_6s": ["6 秒", "6s"],
        "play_25": ["25%"],
        "play_50": ["50%"],
        "play_75": ["75%"],
        "play_complete": ["完播", "100%"],
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

    creative_id_col = cm.get("creative_id")
    if creative_id_col is None and len(df.columns) > 0:
        creative_id_col = df.columns[0]  # First column is always creative ID
    for idx, row in active.iterrows():
        try:
            raw_id = row.get(creative_id_col, idx)
            if isinstance(raw_id, float):
                if raw_id == raw_id:  # not NaN
                    creative_id = str(int(raw_id))
                else:
                    creative_id = str(idx)  # NaN fallback
            else:
                creative_id = str(raw_id) if raw_id is not None else str(idx)
        except (ValueError, OverflowError):
            creative_id = str(idx)
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
            flags["zero_conv"].append((idx, creative_id, cost, row.get(cm["creative"], "") if cm["creative"] else ""))

        if cpm_cap and cpm > cpm_cap and cost > 5:
            flags["cpm_high"].append((idx, creative_id, cpm, row.get(cm["creative"], "") if cm["creative"] else ""))

        if target_cpa and cpa > target_cpa * 1.5 and orders >= 3:
            flags["cpa_high"].append((idx, creative_id, cpa, row.get(cm["creative"], "") if cm["creative"] else ""))

        if target_roi and roi > 0 and roi < target_roi * 0.7 and cost > 10:
            flags["roi_low"].append((idx, creative_id, roi, row.get(cm["creative"], "") if cm["creative"] else ""))

        if 0 < orders < 50 and cost > 0:
            flags["learning"].append(idx)

        if days is not None and 14 <= days <= 28 and cost > 10:
            flags["decay_risk"].append(idx)

        if roi > 3 and orders >= 5:
            flags["winners"].append((idx, creative_id, roi, orders, cpa, row.get(cm["creative"], "") if cm["creative"] else ""))

    # === A1-A5 Funnel Analysis ===
    funnel_issues = {"A1_A2": [], "A2_A3": [], "A3_A4": []}
    play_2s_col = cm.get("play_2s")
    play_6s_col = cm.get("play_6s")
    play_comp_col = cm.get("play_complete")
    
    for idx, row in active.iterrows():
        raw = row.get(cm.get("creative_id"), idx)
        if isinstance(raw, float) and raw == raw:
            fid = str(int(raw))
        else:
            fid = str(raw) if raw is not None else str(idx)
        orders = safe_int(row[orders_col]) if orders_col else 0
        cost = safe_float(row[cost_col]) if cost_col else 0
        if cost < 1:
            continue
        ctr = safe_float(row[ctr_col]) if ctr_col else 0
        cvr = safe_float(row[cvr_col]) if cvr_col else 0
        play_2s = safe_float(row[play_2s_col]) if play_2s_col else 0
        play_6s = safe_float(row[play_6s_col]) if play_6s_col else 0
        play_comp = safe_float(row[play_comp_col]) if play_comp_col else 0
        
        # A1->A2: hook effectiveness (2s -> 6s retention)
        if play_2s > 0 and play_6s > 0:
            a1a2_ratio = play_6s / play_2s if play_2s > 0 else 0
            if a1a2_ratio < 0.3 and orders < 3:
                funnel_issues["A1_A2"].append((creative_id, play_2s, play_6s, a1a2_ratio, row.get(cm["creative"], "")))
        # A2->A3: click interest (CTR)
        if ctr < 0.02 and cost > 5 and orders < 3:
            funnel_issues["A2_A3"].append((creative_id, ctr, row.get(cm["creative"], "")))
        # A3->A4: conversion power (CVR)
        if cvr < 0.02 and ctr > 0.02 and cost > 10 and orders < 3:
            funnel_issues["A3_A4"].append((creative_id, cvr, row.get(cm["creative"], "")))

    # === Flash Spend Detection ===
    flash_spend = []
    for idx, row in active.iterrows():
        cost = safe_float(row[cost_col]) if cost_col else 0
        imp = safe_int(row[imp_col]) if imp_col else 0
        orders = safe_int(row[orders_col]) if orders_col else 0
        if imp > 0 and cost > 0:
            cpm = (cost / imp) * 1000
            if cpm > avg_ctr * avg_cvr * avg_price * 1000 * 1.5 and orders == 0:
                fs_raw = row.get(cm.get("creative_id"), idx)
                if isinstance(fs_raw, float) and fs_raw == fs_raw:
                    fs_id = str(int(fs_raw))
                else:
                    fs_id = str(fs_raw) if fs_raw is not None else str(idx)
                flash_spend.append((fs_id, cpm, cost, row.get(cm["creative"], "")))

    # === Cold Start Phase ===
    learning_count = len(flags["learning"])
    total_conv = sum(safe_int(row[orders_col]) for _, row in active.iterrows()) if orders_col else 0
    if total_conv < 50:
        phase = "探索期"
        phase_note = "系统正在学习，ROI波动正常，勿干预"
    elif total_conv < 200:
        phase = "稳定期"
        phase_note = "CPA逐步稳定，开始关注ROI"
    else:
        phase = "放量期"
        phase_note = "可考虑降低出价、复制优胜素材"
    
    # Decay check
    decaying = [idx for idx in flags["decay_risk"] if idx in [w[0] for w in flags["winners"]]]
    if decaying:
        phase = "衰退期（优胜素材老化）"
        phase_note = "紧急准备新素材替代"

    # === GPM ===
    gpm = avg_price * avg_ctr * avg_cvr * 1000 if avg_ctr > 0 and avg_cvr > 0 else 0

    # === Starting Bid ===
    if target_cpa:
        start_bid_low = target_cpa * 1.2
        start_bid_high = target_cpa * 1.5

    # Status breakdown
    status_counts = df[status_col].value_counts() if status_col else pd.Series()

    # Column mapping info
    col_info = {k: v for k, v in cm.items() if v is not None}

    return {
        "total_creatives": len(df),
        "funnel_issues": funnel_issues,
        "flash_spend": flash_spend,
        "phase": phase,
        "phase_note": phase_note,
        "gpm": gpm,
        "start_bid_low": start_bid_low if target_cpa else None,
        "start_bid_high": start_bid_high if target_cpa else None,
        "total_conv": total_conv,
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
    print(f"  GMV Max 素材诊断  |  {cname}")
    print("=" * 65)
    print(f"  素材总数:        {r['total_creatives']}")
    print(f"  在投数:            {r['active_creatives']}")
    print()
    print(f"  总花费:            ${r['total_cost']:,.2f}")
    print(f"  总订单:            {r['total_orders']}")
    print(f"  总收入:            ${r['total_revenue']:,.2f}")
    print(f"  整体ROI:          {r['overall_roi']:.2f}")
    print(f"  平均客单价:        ${r['avg_price']:.2f}")
    print(f"  平均CPA:         ${r['avg_cpa']:.2f}")
    print(f"  平均CTR:         {r['avg_ctr']*100:.2f}%")
    print(f"  平均CVR:         {r['avg_cvr']*100:.2f}%")
    print()

    fee_rate = r["fee_rate"]
    print(f"  平台费率:         {fee_rate*100:.1f}%")
    if r["be_roi"] is not None:
        be_str = f"{r['be_roi']:.2f}" if r['be_roi'] != float("inf") else "INF"
        print(f"  盈亏平衡ROI:     {be_str}")
    if r.get("be_roi") is not None and r["be_roi"] != float("inf") and r["avg_price"] > 0:
        print(f"  盈亏平衡CPA:     ${r['avg_price']/r['be_roi']:.2f}")
    if r["cpm_cap"] is not None:
        print(f"  CPM上限:           ${r['cpm_cap']:.2f}")
    if r.get("gpm", 0) > 0:
        print(f"  GPM:               ${r['gpm']:.2f}")
    if r.get("start_bid_low"):
        print(f"  建议出价:          ${r['start_bid_low']:.2f} ~ ${r['start_bid_high']:.2f}")
    print()

    # Cold start phase
    if r.get("phase"):
        print(f"  冷启动阶段: {r['phase']}  ({r.get('phase_note', '')})")
        print()

    if len(r["status_counts"]) > 0:
        print("--- 状态分布 ---")
        for status, count in r["status_counts"].items():
            print(f"  {status}: {count}")
        print()

    flags = r["flags"]

    if flags["winners"]:
        print(f"[优胜] {len(flags['winners'])} 个 (ROI>3, >=5单):")
        for _, cid, roi_val, orders, cpa_val, creative in sorted(flags["winners"], key=lambda x: -x[2]):
            c = str(creative)[:60]
            print(f"  {cid}  {roi_val:.1f}  {orders}单  ${cpa_val:.2f}  |  {c}")
        print()

    if flags["zero_conv"]:
        print(f"[淘汰] {len(flags['zero_conv'])} 个 (3天+ 零转化):")
        for _, cid, cost_val, creative in flags["zero_conv"]:
            c = str(creative)[:60]
            print(f"  {cid}  ${cost_val:.2f}  |  {c}")
        print()

    if flags["cpm_high"]:
        print(f"[CPM超标] {len(flags['cpm_high'])} 个:")
        for _, cid, cpm_val, creative in sorted(flags["cpm_high"], key=lambda x: -x[2]):
            c = str(creative)[:60]
            print(f"  {cid}  ${cpm_val:.2f}  |  {c}")
        print()

    if flags["cpa_high"]:
        print(f"[CPA偏高] {len(flags['cpa_high'])} 个:")
        for _, cid, cpa_val, creative in sorted(flags["cpa_high"], key=lambda x: -x[2]):
            c = str(creative)[:60]
            print(f"  {cid}  ${cpa_val:.2f}  |  {c}")
        print()

    if flags["roi_low"]:
        print(f"[ROI偏低] {len(flags['roi_low'])} 个:")
        for _, cid, roi_val, creative in sorted(flags["roi_low"], key=lambda x: x[2]):
            c = str(creative)[:60]
            print(f"  {cid}  {roi_val:.2f}  |  {c}")
        print()

    if flags["learning"]:
        print(f"[学习中] {len(flags['learning'])} 个 (<50单)")
        print("  勿动，让系统学习。")
        print()

    # A1-A5 Funnel Diagnosis
    fi = r.get("funnel_issues", {})
    if fi:
        print("--- A1-A5 漏斗诊断 ---")
        if fi.get("A1_A2"):
            print(f"  [A1→A2 钩子弱] {len(fi['A1_A2'])} 个 (6s/2s留存率<30%):")
            for cid, p2, p6, ratio, creative in fi["A1_A2"]:
                c = str(creative)[:50]
                print(f"    {cid}  2s={p2*100:.0f}%  6s={p6*100:.0f}%  留存={ratio*100:.0f}%  |  {c}")
        if fi.get("A2_A3"):
            print(f"  [A2→A3 点击差] {len(fi['A2_A3'])} 个 (CTR<2%):")
            for cid, ctr_val, creative in fi["A2_A3"]:
                c = str(creative)[:50]
                print(f"    {cid}  CTR={ctr_val*100:.1f}%  |  {c}")
        if fi.get("A3_A4"):
            print(f"  [A3→A4 转化低] {len(fi['A3_A4'])} 个 (CVR<2%):")
            for cid, cvr_val, creative in fi["A3_A4"]:
                c = str(creative)[:50]
                print(f"    {cid}  CVR={cvr_val*100:.1f}%  |  {c}")
        if not any(fi.values()):
            print("  漏斗健康，无明显断点。")
        print()

    # Flash spend
    fs = r.get("flash_spend", [])
    if fs:
        print(f"[闪烧预警] {len(fs)} 个素材CPM异常高且零转化:")
        for cid, cpm_val, cost_val, creative in fs:
            c = str(creative)[:40]
            print(f"  {cid}  CPM=${cpm_val:.2f}  花费=${cost_val:.2f}  |  {c}")
        print()

    if flags["decay_risk"]:
        print(f"[衰退风险] {len(flags['decay_risk'])} 个 (14-28天)")
        print("  提前准备新素材。")
        print()

    print("--- 建议 ---")
    recs = []
    if flags["zero_conv"]:
        recs.append(f"淘汰 {len(flags['zero_conv'])} 个零转化素材 (3天+)")
    if flags["cpm_high"]:
        recs.append(f"检查 {len(flags['cpm_high'])} 个 CPM超标素材")
    if flags["roi_low"]:
        recs.append(f"关注 {len(flags['roi_low'])} 个 ROI偏低素材")
    if flags["winners"]:
        recs.append(f"放大: 复制 {len(flags['winners'])} 个优胜素材风格")
    if flags["decay_risk"]:
        recs.append(f"预备新素材替换 {len(flags['decay_risk'])} 个衰退素材")
    if flags["learning"]:
        recs.append(f"保护 {len(flags['learning'])} 个学习中素材: 勿暂停/重启")
    if not recs:
        recs.append("账户健康，保持每日素材更新。")
    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")

    if r["be_roi"] is not None:
        print()
        print("--- CPM 参考 ---")
        print(f"  盈亏平衡ROI: {r['be_roi']:.2f}")
        for mult in [1.3, 1.5, 2.0]:
            troi = r["be_roi"] * mult
            gpm = r["avg_price"] * r["avg_ctr"] * r["avg_cvr"] * 1000
            cap = gpm / troi if troi > 0 else 999
            print(f"  {mult}x (ROI={troi:.1f}): CPM上限=${cap:.2f}, CPA目标=${r['avg_price']/troi:.2f}")
        daily = (r["avg_price"] / (r["be_roi"] * 1.3)) * 50 if r["be_roi"] > 0 else 0
        print(f"  建议日预算: ${daily:.2f}")

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
