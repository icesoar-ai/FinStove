"""Streamlit 数据看板 Demo — 展示项目数据的 Web 交互界面."""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="金融分析看板", layout="wide")
st.title("金融分析助手 — 数据看板")

# Sidebar
st.sidebar.header("筛选")
market_filter = st.sidebar.selectbox("市场", ["全部", "美股", "港股", "欧洲", "亚太", "A股"])
time_range = st.sidebar.selectbox("时间范围", ["1周", "1月", "3月", "6月", "1年"])

# Read data from Parquet
def load_index_data():
    """Load global index data from Parquet."""
    storage = Path("data/index")
    targets = [
        ("us", "SPX", "S&P 500", "美股"),
        ("us", "NDX", "Nasdaq", "美股"),
        ("us", "DJI", "Dow Jones", "美股"),
        ("hk", "HSI", "恒生指数", "港股"),
        ("jp", "N225", "日经225", "亚太"),
        ("de", "DAX", "DAX 40", "欧洲"),
        ("uk", "FTSE", "FTSE 100", "欧洲"),
    ]
    results = []
    for mkt, sym, label, group in targets:
        f = storage / mkt / sym / "daily.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            if "close" in df.columns and "date" in df.columns:
                df = df.sort_values("date")
                close = df["close"].astype(float)
                latest = close.iloc[-1]
                chg_1d = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0
                chg_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
                results.append({
                    "品种": label, "分组": group, "最新价": f"{latest:,.0f}",
                    "1日": chg_1d, "5日": chg_5d,
                })
    return pd.DataFrame(results)

def load_macro_summary():
    """Summary of macro data."""
    import json
    results = []
    macro_dir = Path("data/macro/cn")
    indicator_labels = {
        "cpi": ("CPI 同比", "%"), "ppi": ("PPI 同比", "%"),
        "pmi": ("制造业PMI", ""), "gdp": ("GDP 增速", "%"),
        "money_supply": ("M2 同比", "%"), "lpr": ("LPR 1Y", "%"),
        "exports_yoy": ("出口同比", "%"), "fx_reserves": ("外汇储备", "亿$"),
    }
    for code, (label, unit) in indicator_labels.items():
        f = macro_dir / code / "monthly.parquet"
        if not f.exists():
            f = macro_dir / code / "quarterly.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            # Find latest value
            if "今值" in df.columns:
                vals = [v for v in df["今值"].tolist() if pd.notna(v) and v != 0]
                if vals:
                    results.append({"指标": label, "最新值": f"{vals[-1]:.1f}{unit}"})
            elif "同比增长" in df.columns:
                vals = [v for v in df["同比增长"].tolist() if pd.notna(v)]
                if vals:
                    results.append({"指标": label, "最新值": f"{vals[-1]:.1f}{unit}"})
    return pd.DataFrame(results) if results else pd.DataFrame({"指标": [], "最新值": []})

# Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("全球指数")
    df_idx = load_index_data()
    if not df_idx.empty:
        if market_filter != "全部":
            df_idx = df_idx[df_idx["分组"] == market_filter]

        # Color-coded changes
        def color_chg(val):
            if isinstance(val, (int, float)):
                color = "green" if val > 0 else "red"
                return f"color: {color}"
            return ""

        styled = df_idx.style.map(color_chg, subset=["1日", "5日"]).format({"1日": "{:+.1f}%", "5日": "{:+.1f}%"})
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Mini chart
        st.subheader("S&P 500 走势")
        spx_f = Path("data/index/us/SPX/daily.parquet")
        if spx_f.exists():
            spx_df = pd.read_parquet(spx_f).sort_values("date")
            days_map = {"1周": 5, "1月": 21, "3月": 63, "6月": 126, "1年": 252}
            n = days_map.get(time_range, 63)
            chart_data = spx_df[["date", "close"]].tail(n).set_index("date")
            chart_data.columns = ["S&P 500"]
            st.line_chart(chart_data, height=300)

with col2:
    st.subheader("中国宏观")
    df_macro = load_macro_summary()
    if not df_macro.empty:
        st.dataframe(df_macro, use_container_width=True, hide_index=True)

    st.subheader("最新信号")
    macro_dir = Path("data/macro/cn")
    signals = []
    # PMI signal
    pmi_f = macro_dir / "pmi" / "monthly.parquet"
    if pmi_f.exists():
        df = pd.read_parquet(pmi_f)
        if "今值" in df.columns:
            vals = [v for v in df["今值"].tolist() if pd.notna(v)]
            if vals:
                pmi_val = vals[-1]
                if pmi_val > 50:
                    signals.append(("PMI", "扩张", "green"))
                else:
                    signals.append(("PMI", "收缩", "red"))
    # CPI signal
    cpi_f = macro_dir / "cpi" / "monthly.parquet"
    if cpi_f.exists():
        df = pd.read_parquet(cpi_f)
        if "今值" in df.columns:
            vals = [v for v in df["今值"].tolist() if pd.notna(v)]
            if vals:
                cpi_val = vals[-1]
                if 0 < cpi_val < 2:
                    signals.append(("CPI", "温和", "green"))
                elif cpi_val < 0:
                    signals.append(("CPI", "通缩", "red"))
                else:
                    signals.append(("CPI", "偏高", "orange"))

    for name, status, color in signals:
        st.markdown(f"- **{name}**: :{color}[{status}]")

st.divider()
st.caption("数据来源: AKShare / YFinance / FRED | 更新: Parquet 存储")
