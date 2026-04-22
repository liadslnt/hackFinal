from __future__ import annotations

from pathlib import Path
import csv

import pandas as pd
import streamlit as st

from trade_risk_analysis import build_mirror_dataset, default_output_path, load_dataset, save_dataset

st.set_page_config(page_title="Lithium Mirror Risk Intelligence", page_icon=":bar_chart:", layout="wide")

PROJECT_DIR = Path(__file__).resolve().parent
PRODUCT_PRESETS = {
    "253090": "253090 - Other mineral substances",
    "283691": "283691 - Lithium carbonate",
    "282520": "282520 - Lithium oxide and hydroxide",
    "850760": "850760 - Lithium-ion batteries (public-source coverage may fail)",
}
ARGENTINA_CHART_PATH = PROJECT_DIR / "argentina_mirror_trade_quarterly_2024.png"
ARGENTINA_SODIUM_FILE = PROJECT_DIR / "TradeData_4_22_2026_12_56_0.csv"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Manrope:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f4f0e8;
            --surface: rgba(255, 255, 255, 0.78);
            --surface-strong: rgba(255, 255, 255, 0.92);
            --ink: #14213d;
            --muted: #526173;
            --line: rgba(20, 33, 61, 0.10);
            --accent: #c96d32;
            --accent-soft: rgba(201, 109, 50, 0.12);
            --high: #a83232;
            --medium: #b67a1f;
            --low: #2e7d5b;
            --shadow: 0 20px 40px rgba(20, 33, 61, 0.08);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(201, 109, 50, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(20, 33, 61, 0.09), transparent 24%),
                linear-gradient(180deg, #f7f2ea 0%, #efe8dd 100%);
            color: var(--ink);
            font-family: "Manrope", sans-serif;
        }

        h1, h2, h3, h4 {
            font-family: "Space Grotesk", sans-serif !important;
            color: var(--ink);
            letter-spacing: -0.02em;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #17324d 0%, #0f2439 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * {
            color: #f7f3ee !important;
        }

        [data-testid="stSidebar"] .stCodeBlock,
        [data-testid="stSidebar"] code {
            color: #f3d7bf !important;
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2.5rem;
            max-width: 1380px;
        }

        .hero-shell {
            background:
                linear-gradient(135deg, rgba(20, 33, 61, 0.96) 0%, rgba(27, 52, 81, 0.94) 58%, rgba(201, 109, 50, 0.90) 100%);
            color: #fff8f1;
            border-radius: 28px;
            padding: 1.8rem 2rem;
            box-shadow: var(--shadow);
            border: 1px solid rgba(255, 255, 255, 0.10);
            margin-bottom: 1.25rem;
            overflow: hidden;
        }

        .hero-kicker {
            display: inline-block;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.18);
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.8rem;
        }

        .hero-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 2.4rem;
            line-height: 1.02;
            margin: 0 0 0.6rem 0;
            color: #fff8f1;
        }

        .hero-text {
            max-width: 880px;
            color: rgba(255, 248, 241, 0.86);
            font-size: 1rem;
            line-height: 1.6;
            margin-bottom: 0.9rem;
        }

        .hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            margin-top: 1rem;
        }

        .hero-chip {
            padding: 0.5rem 0.8rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.16);
            font-size: 0.9rem;
        }

        .section-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 24px;
            padding: 1.15rem 1.2rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(12px);
        }

        .section-card + .section-card {
            margin-top: 1rem;
        }

        .risk-banner {
            padding: 1rem 1.15rem;
            border-radius: 20px;
            border: 1px solid transparent;
            margin-bottom: 1rem;
        }

        .risk-banner.high {
            background: rgba(168, 50, 50, 0.10);
            border-color: rgba(168, 50, 50, 0.16);
        }

        .risk-banner.medium {
            background: rgba(182, 122, 31, 0.12);
            border-color: rgba(182, 122, 31, 0.16);
        }

        .risk-banner.low {
            background: rgba(46, 125, 91, 0.10);
            border-color: rgba(46, 125, 91, 0.16);
        }

        .risk-label {
            display: inline-block;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            font-weight: 800;
            letter-spacing: 0.05em;
            font-size: 0.78rem;
            margin-bottom: 0.55rem;
        }

        .risk-label.high {
            background: rgba(168, 50, 50, 0.16);
            color: var(--high);
        }

        .risk-label.medium {
            background: rgba(182, 122, 31, 0.16);
            color: var(--medium);
        }

        .risk-label.low {
            background: rgba(46, 125, 91, 0.16);
            color: var(--low);
        }

        .risk-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.35rem;
            margin: 0 0 0.25rem 0;
        }

        .risk-subtext {
            color: var(--muted);
            line-height: 1.55;
            margin: 0;
        }

        .stat-card {
            background: var(--surface-strong);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            min-height: 126px;
            box-shadow: var(--shadow);
        }

        .stat-label {
            color: var(--muted);
            font-size: 0.9rem;
            margin-bottom: 0.55rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            color: var(--ink);
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.65rem;
            line-height: 1.1;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }

        .stat-note {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .mini-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0.75rem;
            margin-top: 0.95rem;
        }

        .mini-tile {
            background: rgba(20, 33, 61, 0.03);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 0.9rem;
        }

        .mini-tile-label {
            font-size: 0.82rem;
            color: var(--muted);
            margin-bottom: 0.35rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .mini-tile-value {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.2rem;
            color: var(--ink);
            font-weight: 700;
        }

        .eyebrow {
            color: var(--accent);
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .body-copy {
            color: var(--muted);
            line-height: 1.65;
            font-size: 0.97rem;
        }

        .reason-list {
            margin: 0.75rem 0 0 0;
            padding-left: 1.15rem;
            color: var(--ink);
        }

        .reason-list li {
            margin-bottom: 0.45rem;
            line-height: 1.5;
        }

        .table-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.05rem;
            color: var(--ink);
            margin-bottom: 0.65rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.55rem;
            margin-bottom: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.58);
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.55rem 0.95rem;
            font-weight: 700;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #17324d 0%, #c96d32 100%) !important;
            color: #fff7ef !important;
            border-color: transparent !important;
        }

        div[data-testid="stMetric"] {
            background: var(--surface-strong);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            box-shadow: var(--shadow);
        }

        div[data-testid="stDataFrame"] {
            background: var(--surface-strong);
            border-radius: 18px;
            border: 1px solid var(--line);
            padding: 0.35rem;
            box-shadow: var(--shadow);
        }

        [data-testid="stImage"] img {
            border-radius: 20px;
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_usd(value: float) -> str:
    return f"${value:,.0f}"


def format_kg(value: float) -> str:
    return f"{value:,.0f} kg"


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def format_int(value: float) -> str:
    return f"{value:,.0f}"


def risk_css_class(risk: str) -> str:
    return str(risk).strip().lower()


def safe_reason_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def signal_direction_text(reported_exports_kg: float, mirror_imports_kg: float) -> str:
    if mirror_imports_kg > reported_exports_kg:
        return "The world reports receiving more from this country than the country says it exported."
    if mirror_imports_kg < reported_exports_kg:
        return "This country reports exporting more than the rest of the world reports importing from it."
    return "Reported exports and mirror imports are closely aligned."


def render_stat_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
            <div class="stat-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_intro_hero() -> None:
    st.markdown(
        """
        <section class="hero-shell">
            <div class="hero-kicker">Supply Chain Intelligence</div>
            <div class="hero-title">Lithium Mirror Trade Risk Intelligence</div>
            <div class="hero-text">
                Explore trade inconsistencies country by country using official public trade data.
                The platform compares what an exporter declares with what the rest of the world says it imported,
                then turns that discrepancy into a risk signal that is easier to investigate.
            </div>
            <div class="hero-meta">
                <div class="hero-chip">Official WITS / Comtrade inputs</div>
                <div class="hero-chip">Mirror-trade gap detection</div>
                <div class="hero-chip">Volume-normalized risk scoring</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_country_header(country: str, risk: str, year: int, product_name: str) -> None:
    risk_class = risk_css_class(risk)
    st.markdown(
        f"""
        <div class="risk-banner {risk_class}">
            <div class="risk-label {risk_class}">{risk} RISK</div>
            <div class="risk-title">{country}</div>
            <p class="risk-subtext">
                {product_name} in {year}. This view compares the country's declared exports against
                the mirror imports reported by all partner countries.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_summary(country_row: pd.Series) -> None:
    reported_exports_kg = float(country_row["reported_exports_kg"])
    mirror_imports_kg = float(country_row["mirror_imports_kg"])
    gap_kg = float(country_row["gap_kg"])
    gap_pct = float(country_row["gap_pct"])
    reasons = safe_reason_list(country_row.get("reasons", []))
    rule_summary = str(country_row.get("rule_summary", "")).strip()

    summary_text = (
        f"For this country, reported exports reach <strong>{format_kg(reported_exports_kg)}</strong> while "
        f"mirror imports reach <strong>{format_kg(mirror_imports_kg)}</strong>. "
        f"That creates a discrepancy of <strong>{format_kg(gap_kg)}</strong>, equal to "
        f"<strong>{format_pct(gap_pct)}</strong> of reported exports."
    )
    direction_text = signal_direction_text(reported_exports_kg, mirror_imports_kg)

    reason_items = "".join(f"<li>{reason}</li>" for reason in reasons) if reasons else "<li>No additional reasons available.</li>"

    st.markdown(
        f"""
        <div class="section-card">
            <div class="eyebrow">Signal Summary</div>
            <div class="body-copy">{summary_text}</div>
            <div class="mini-grid">
                <div class="mini-tile">
                    <div class="mini-tile-label">Interpretation</div>
                    <div class="mini-tile-value">{country_row["risk"]}</div>
                </div>
                <div class="mini-tile">
                    <div class="mini-tile-label">Gap Direction</div>
                    <div class="mini-tile-value">{'Mirror > Reported' if mirror_imports_kg > reported_exports_kg else 'Reported > Mirror' if mirror_imports_kg < reported_exports_kg else 'Aligned'}</div>
                </div>
                <div class="mini-tile">
                    <div class="mini-tile-label">Physical Gap</div>
                    <div class="mini-tile-value">{format_kg(gap_kg)}</div>
                </div>
                <div class="mini-tile">
                    <div class="mini-tile-label">Relative Gap</div>
                    <div class="mini-tile-value">{format_pct(gap_pct)}</div>
                </div>
            </div>
            <div style="margin-top: 1rem;" class="body-copy">{direction_text}</div>
            {f'<div style="margin-top: 0.8rem;" class="body-copy"><strong>Scoring note:</strong> {rule_summary}</div>' if rule_summary else ''}
            <ul class="reason-list">{reason_items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def prettify_partner_table(table: pd.DataFrame) -> pd.DataFrame:
    pretty = table.copy()
    if "partner" in pretty.columns:
        pretty = pretty.rename(columns={"partner": "Partner"})
    if "value_usd" in pretty.columns:
        pretty["value_usd"] = pd.to_numeric(pretty["value_usd"], errors="coerce").fillna(0.0).map(format_usd)
        pretty = pretty.rename(columns={"value_usd": "Trade value"})
    if "quantity_kg" in pretty.columns:
        pretty["quantity_kg"] = pd.to_numeric(pretty["quantity_kg"], errors="coerce").fillna(0.0).map(format_kg)
        pretty = pretty.rename(columns={"quantity_kg": "Quantity"})
    if "share_pct" in pretty.columns:
        pretty["share_pct"] = pd.to_numeric(pretty["share_pct"], errors="coerce").fillna(0.0).map(format_pct)
        pretty = pretty.rename(columns={"share_pct": "Share"})
    return pretty


def load_argentina_sodium_signal(path_str: str) -> dict | None:
    path = Path(path_str)
    if not path.exists():
        fallback = PROJECT_DIR / path.name
        if fallback.exists():
            path = fallback
        else:
            return None

    raw_bytes = path.read_bytes()
    decoded_text = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            decoded_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        return None

    records = list(csv.DictReader(decoded_text.splitlines()))
    if not records:
        return None

    df = pd.DataFrame(records).fillna("")

    required_cols = {"reporterISO", "flowDesc", "cmdCode", "refYear", "partnerISO", "partnerDesc"}
    if not required_cols.issubset(df.columns):
        return None

    for col in ["reporterISO", "partnerISO", "flowDesc", "cmdCode", "partnerDesc", "cmdDesc"]:
        df[col] = df[col].astype(str).str.strip()

    for col in ["refYear", "refMonth", "altQty", "netWgt", "primaryValue"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df[
        (df["reporterISO"] == "ARG")
        & (df["flowDesc"].str.lower() == "import")
        & (df["cmdCode"] == "283620")
        & (df["refYear"] == 2024)
    ].copy()

    if df.empty:
        return None

    df["quantity_kg"] = 0.0
    if "altQty" in df.columns:
        alt_mask = df["altQty"].gt(0)
        df.loc[alt_mask, "quantity_kg"] = df.loc[alt_mask, "altQty"]
    if "netWgt" in df.columns:
        zero_mask = df["quantity_kg"].eq(0.0)
        df.loc[zero_mask, "quantity_kg"] = df.loc[zero_mask, "netWgt"]

    world_rows = df[df["partnerISO"] == "W00"].copy()
    if world_rows.empty:
        return None

    monthly = (
        world_rows.groupby("refMonth", as_index=False)["quantity_kg"]
        .sum()
        .sort_values("refMonth")
        .reset_index(drop=True)
    )
    total_kg = float(monthly["quantity_kg"].sum())
    peak_row = monthly.loc[monthly["quantity_kg"].idxmax()]

    supplier_rows = df[df["partnerISO"] != "W00"].copy()
    top_suppliers = (
        supplier_rows.groupby("partnerDesc", as_index=False)["quantity_kg"]
        .sum()
        .sort_values("quantity_kg", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )
    top_suppliers["share_pct"] = (
        top_suppliers["quantity_kg"] / max(total_kg, 1.0) * 100.0
    )

    return {
        "product": str(world_rows["cmdDesc"].iloc[0]).strip() if "cmdDesc" in world_rows.columns else "Sodium carbonate",
        "total_kg": total_kg,
        "peak_month": int(peak_row["refMonth"]),
        "peak_month_kg": float(peak_row["quantity_kg"]),
        "monthly": monthly.to_dict(orient="records"),
        "top_suppliers": top_suppliers.to_dict(orient="records"),
    }


@st.cache_data(show_spinner=False)
def load_cached_dataset(product_code: str, year: int) -> pd.DataFrame:
    path = default_output_path(product_code, year)
    records = load_dataset(path)
    return pd.DataFrame(records)


def build_live_dataset(product_code: str, year: int, sleep_seconds: float) -> pd.DataFrame:
    dataset = build_mirror_dataset(year=year, product_code=product_code, sleep_seconds=sleep_seconds)
    save_dataset(dataset, default_output_path(product_code, year))
    return pd.DataFrame(dataset)


def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for col in [
        "reported_exports_usd",
        "mirror_imports_usd",
        "gap_usd",
        "reported_exports_kg",
        "mirror_imports_kg",
        "gap_kg",
        "gap_pct",
    ]:
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce").fillna(0.0)
    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    normalized["risk_sort"] = normalized["risk"].map(risk_order).fillna(99)
    normalized = normalized.sort_values(
        ["risk_sort", "gap_pct", "country"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
    return normalized


inject_styles()
render_intro_hero()

st.markdown(
    """
    <div class="section-card" style="margin-bottom: 1rem;">
        <div class="eyebrow">What This Tool Does</div>
        <div class="body-copy">
            Pick an HS code and a year. The app fetches or loads the relevant dataset, then compares
            each country's declared exports with the mirror imports declared by the rest of the world.
            Risk is based on both percentage gap and absolute traded volume, so tiny flows are not treated the same way as large industrial ones.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Query")
    preset_label = st.selectbox(
        "Choose a product",
        options=list(PRODUCT_PRESETS.values()),
        index=1,
    )
    preset_code = next(code for code, label in PRODUCT_PRESETS.items() if label == preset_label)
    use_custom_code = st.checkbox("Use a custom HS code", value=False)
    hs_code = st.text_input(
        "HS code",
        value=st.session_state.get("hs_code", preset_code) if use_custom_code else preset_code,
    ).strip()
    year = st.selectbox("Year", options=list(range(2024, 2001, -1)), index=0)
    sleep_seconds = st.slider("Request spacing (seconds)", min_value=0.0, max_value=1.0, value=0.25, step=0.05)
    st.markdown("---")
    st.caption("Examples")
    st.code("\n".join(PRODUCT_PRESETS.values()))
    run_fetch = st.button("Fetch Official Data", type="primary", use_container_width=True)
    load_cache = st.button("Load Cached Data", use_container_width=True)

if hs_code == "850760":
    st.info(
        "HS 850760 uses your local Comtrade CSV when available, because public web coverage can be unstable for this code."
    )

if "dataset_df" not in st.session_state:
    st.session_state["dataset_df"] = None
if "dataset_key" not in st.session_state:
    st.session_state["dataset_key"] = None
if "hs_code" not in st.session_state:
    st.session_state["hs_code"] = hs_code

if run_fetch:
    st.session_state["hs_code"] = hs_code
    try:
        if hs_code == "283691" and year == 2024 and Path(default_output_path(hs_code, year)).exists():
            df = load_cached_dataset(product_code=hs_code, year=year)
            st.session_state["dataset_df"] = normalize_numeric_columns(df)
            st.session_state["dataset_key"] = (hs_code, year)
            st.success("Loaded the precomputed carbonate demo dataset instantly.")
        else:
            with st.spinner(f"Fetching official trade data for HS {hs_code} in {year}. This can take around a minute."):
                df = build_live_dataset(product_code=hs_code, year=year, sleep_seconds=sleep_seconds)
                st.session_state["dataset_df"] = normalize_numeric_columns(df)
                st.session_state["dataset_key"] = (hs_code, year)
                st.success(f"Official dataset fetched for HS {hs_code} in {year}.")
    except Exception as exc:
        st.error(str(exc))

if load_cache:
    st.session_state["hs_code"] = hs_code
    try:
        df = load_cached_dataset(product_code=hs_code, year=year)
        st.session_state["dataset_df"] = normalize_numeric_columns(df)
        st.session_state["dataset_key"] = (hs_code, year)
        st.success(f"Loaded cached dataset for HS {hs_code} in {year}.")
    except Exception as exc:
        st.error(str(exc))

df = st.session_state.get("dataset_df")
dataset_key = st.session_state.get("dataset_key")

if df is None:
    st.markdown(
        """
        <div class="section-card">
            <div class="eyebrow">Start Here</div>
            <div class="body-copy">
                Choose an HS code and a year in the left panel, then click <strong>Fetch Official Data</strong>.
                If you already generated that dataset once, use <strong>Load Cached Data</strong> for a faster demo flow.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

current_hs, current_year = dataset_key
product_name = df["product"].iloc[0] if "product" in df.columns and not df.empty else current_hs

with st.sidebar:
    st.markdown("---")
    st.header("Loaded Dataset")
    st.metric("HS code", str(current_hs))
    st.metric("Year", str(current_year))
    st.metric("HIGH", int((df["risk"] == "HIGH").sum()))
    st.metric("MEDIUM", int((df["risk"] == "MEDIUM").sum()))
    st.metric("LOW", int((df["risk"] == "LOW").sum()))

top_header_left, top_header_right = st.columns([1.8, 1.1])
with top_header_left:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="eyebrow">Loaded Scope</div>
            <div class="body-copy">
                <strong>HS {current_hs}</strong> · {product_name} · <strong>{current_year}</strong><br>
                Search a country below to inspect its mirror-trade discrepancy and supporting partner evidence.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with top_header_right:
    risk_counts = (
        f"{int((df['risk'] == 'HIGH').sum())} HIGH / "
        f"{int((df['risk'] == 'MEDIUM').sum())} MEDIUM / "
        f"{int((df['risk'] == 'LOW').sum())} LOW"
    )
    st.markdown(
        f"""
        <div class="section-card">
            <div class="eyebrow">Dataset Snapshot</div>
            <div class="body-copy">
                <strong>{len(df):,}</strong> exporter countries scored.<br>
                Distribution: <strong>{risk_counts}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

search_col, hint_col = st.columns([1.5, 1])
country_options = sorted(df["country"].dropna().astype(str).unique().tolist())
default_country = "Argentina" if "Argentina" in country_options else ("Chile" if "Chile" in country_options else country_options[0])
default_index = country_options.index(default_country)

with search_col:
    selected_country = st.selectbox("Country", options=country_options, index=default_index)
with hint_col:
    search_text = st.text_input("Quick search", value=selected_country, placeholder="Type a country name")

match_df = (
    df[df["country"].str.contains(search_text.strip(), case=False, na=False)].copy()
    if search_text.strip()
    else df.iloc[0:0].copy()
)

if match_df.empty:
    st.warning("No country found for this search.")
    st.stop()

exact_match = match_df[match_df["country"].str.lower() == search_text.strip().lower()]
country_row = exact_match.iloc[0] if not exact_match.empty else match_df.iloc[0]

render_country_header(country_row["country"], country_row["risk"], current_year, product_name)

metric_cols = st.columns(4)
with metric_cols[0]:
    render_stat_card(
        "Reported exports",
        format_kg(float(country_row["reported_exports_kg"])),
        "Quantity declared by the exporter country.",
    )
with metric_cols[1]:
    render_stat_card(
        "Mirror imports",
        format_kg(float(country_row["mirror_imports_kg"])),
        "Quantity reported by all partner countries from this exporter.",
    )
with metric_cols[2]:
    render_stat_card(
        "Absolute gap",
        format_kg(float(country_row["gap_kg"])),
        "Physical discrepancy between the two views.",
    )
with metric_cols[3]:
    render_stat_card(
        "Gap ratio",
        format_pct(float(country_row["gap_pct"])),
        "Gap as a share of reported exports.",
    )

render_signal_summary(country_row)

overview_tab, partners_tab, evidence_tab, ranking_tab = st.tabs(
    ["Overview", "Partner Flows", "Evidence & Sources", "Full Ranking"]
)

with overview_tab:
    left, right = st.columns([1.15, 0.85])
    is_argentina_demo_case = (
        str(current_hs) == "283691"
        and str(current_year) == "2024"
        and str(country_row["country"]) == "Argentina"
    )
    with left:
        st.markdown(
            """
            <div class="section-card">
                <div class="eyebrow">How Risk Is Calculated</div>
                <div class="body-copy">
                    The model compares the country's reported exports against mirror imports reported by the rest of the world.
                    It uses both relative discrepancy and absolute physical volume, so a tiny exporter with a big percentage gap is not automatically treated like a large industrial anomaly.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Open scoring logic"):
            st.write("Below 100,000 kg exports: always LOW")
            st.write("100,000 to 500,000 kg exports: risk is capped unless the gap is extremely large")
            st.write("500,000 to 5,000,000 kg exports: MEDIUM or HIGH requires both a large % gap and a large kg gap")
            st.write("Above 5,000,000 kg exports: MEDIUM starts at 10% + 500,000 kg, HIGH starts at 30% + 2,000,000 kg")
    with right:
        if is_argentina_demo_case:
            st.markdown(
                """
                <div class="section-card">
                    <div class="eyebrow">Argentina Investigation Focus</div>
                    <div class="body-copy">
                        For the demo, Argentina is our main investigation case. The mirror gap suggests that trade reporting
                        does not fully align, so the next checks would focus on three field signals: truck movements around
                        lithium production sites, LinkedIn hiring by major operators, and customs-origin consistency in 2024.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class="section-card" style="margin-top: 1rem;">
                    <div class="eyebrow">Why These Checks Matter</div>
                    <div class="body-copy">
                        If truck activity and hiring both rise sharply, that supports real industrial growth in Argentina.
                        If those on-the-ground signals stay flat while importers still report much higher volumes from Argentina,
                        that becomes a stronger lead for origin misreporting, rerouting, or customs inconsistencies.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="section-card">
                    <div class="eyebrow">What To Investigate Next</div>
                    <div class="body-copy">
                        A high mirror gap does not prove fraud by itself. It is an investigation lead.
                        The next step is to compare this signal with company production, plant activity, customs routing,
                        job postings, shipping patterns, and public disclosures for the same year.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if is_argentina_demo_case:
        sodium_signal = load_argentina_sodium_signal(str(ARGENTINA_SODIUM_FILE))
        st.markdown(
            """
            <div class="section-card" style="margin-top: 1rem;">
                <div class="eyebrow">Quarterly Visual</div>
                <div class="body-copy">
                    2024 only. Each quarter is computed using the average of non-zero months only,
                    so a missing month like January does not artificially pull the trend downward.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if ARGENTINA_CHART_PATH.exists():
            st.image(
                str(ARGENTINA_CHART_PATH),
                caption="Argentina quarterly exports vs mirror imports",
                use_container_width=True,
            )
        else:
            st.info(
                "The quarterly chart file is not generated yet. Run `argentina_monthly_chart.py` once in the project folder."
            )

        if sodium_signal is not None:
            st.markdown(
                f"""
                <div class="section-card" style="margin-top: 1rem;">
                    <div class="eyebrow">Upstream Input Check</div>
                    <div class="body-copy">
                        Argentina imported <strong>{format_kg(float(sodium_signal["total_kg"]))}</strong> of
                        sodium carbonate in 2024 under HS 283620. This is a useful upstream signal because sodium
                        carbonate is an important industrial input for lithium carbonate processing.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            s1, s2, s3 = st.columns(3)
            with s1:
                render_stat_card(
                    "Total sodium imports",
                    format_kg(float(sodium_signal["total_kg"])),
                    "Argentina imports of HS 283620 in 2024.",
                )
            with s2:
                render_stat_card(
                    "Peak month",
                    f"Month {int(sodium_signal['peak_month'])}",
                    "Highest monthly import level in the local Comtrade file.",
                )
            with s3:
                render_stat_card(
                    "Peak-month volume",
                    format_kg(float(sodium_signal["peak_month_kg"])),
                    "Sodium carbonate imported during the peak month.",
                )

            st.markdown(
                """
                <div class="section-card" style="margin-top: 1rem;">
                    <div class="eyebrow">Interpretation</div>
                    <div class="body-copy">
                        This makes Argentina's industrial growth more plausible in 2024, but it does not eliminate
                        the mirror-trade discrepancy. It strengthens the case for real processing activity while
                        keeping the trade mismatch as an investigation lead.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            monthly_sodium = pd.DataFrame(sodium_signal["monthly"]).copy()
            monthly_sodium["refMonth"] = monthly_sodium["refMonth"].map(lambda x: f"M{int(x)}")
            monthly_sodium["quantity_kg"] = monthly_sodium["quantity_kg"].map(format_kg)
            monthly_sodium = monthly_sodium.rename(
                columns={"refMonth": "Month", "quantity_kg": "Sodium carbonate imports"}
            )

            supplier_table = pd.DataFrame(sodium_signal["top_suppliers"]).copy()
            supplier_table["quantity_kg"] = supplier_table["quantity_kg"].map(format_kg)
            supplier_table["share_pct"] = supplier_table["share_pct"].map(format_pct)
            supplier_table = supplier_table.rename(
                columns={
                    "partnerDesc": "Supplier",
                    "quantity_kg": "Quantity",
                    "share_pct": "Share",
                }
            )

            c_months, c_suppliers = st.columns(2)
            with c_months:
                st.markdown('<div class="table-title">Monthly Sodium Imports</div>', unsafe_allow_html=True)
                st.dataframe(monthly_sodium, use_container_width=True, hide_index=True)
            with c_suppliers:
                st.markdown('<div class="table-title">Top Sodium Suppliers</div>', unsafe_allow_html=True)
                st.dataframe(supplier_table, use_container_width=True, hide_index=True)

with partners_tab:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="table-title">Top Declared Export Partners</div>', unsafe_allow_html=True)
        export_partners = pd.DataFrame(country_row["top_export_partners"])
        if not export_partners.empty:
            st.dataframe(prettify_partner_table(export_partners), use_container_width=True, hide_index=True)
        else:
            st.info("No declared export partner details found.")
    with c2:
        st.markdown('<div class="table-title">Top Mirror Importers</div>', unsafe_allow_html=True)
        mirror_importers = pd.DataFrame(country_row["top_mirror_importers"])
        if not mirror_importers.empty:
            st.dataframe(prettify_partner_table(mirror_importers), use_container_width=True, hide_index=True)
        else:
            st.info("No mirror importer details found.")

with evidence_tab:
    st.markdown(
        """
        <div class="section-card">
            <div class="eyebrow">Primary Sources</div>
            <div class="body-copy">
                These are the official public pages or local Comtrade extracts used to construct the signal for this country.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if str(country_row["export_page"]).startswith("local-comtrade-csv://"):
        st.code(str(country_row["export_page"]).replace("local-comtrade-csv://", "Local Comtrade CSV: "))
    else:
        src1, src2 = st.columns(2)
        with src1:
            st.link_button("Open exporter page", str(country_row["export_page"]), use_container_width=True)
        with src2:
            st.link_button("Open mirror import page", str(country_row["mirror_page"]), use_container_width=True)

    st.markdown(
        """
        <div class="section-card" style="margin-top: 1rem;">
            <div class="eyebrow">Matching Countries</div>
            <div class="body-copy">
                Countries matching your search are shown below, which helps if you typed a partial name.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    preview = match_df[["country", "risk", "gap_pct", "reported_exports_kg", "mirror_imports_kg"]].copy()
    preview["gap_pct"] = preview["gap_pct"].map(format_pct)
    preview["reported_exports_kg"] = preview["reported_exports_kg"].map(format_kg)
    preview["mirror_imports_kg"] = preview["mirror_imports_kg"].map(format_kg)
    preview = preview.rename(
        columns={
            "country": "Country",
            "risk": "Risk",
            "gap_pct": "Gap %",
            "reported_exports_kg": "Reported exports",
            "mirror_imports_kg": "Mirror imports",
        }
    )
    st.dataframe(preview, use_container_width=True, hide_index=True)

with ranking_tab:
    top1, top2 = st.columns([1, 2])
    with top1:
        risk_filter = st.multiselect("Filter risk", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM", "LOW"])
    with top2:
        st.markdown(
            """
            <div class="body-copy" style="padding-top: 0.55rem;">
                This table helps you compare all exporter countries for the selected product and year.
            </div>
            """,
            unsafe_allow_html=True,
        )

    table_df = df[df["risk"].isin(risk_filter)][
        ["country", "risk", "gap_pct", "reported_exports_kg", "mirror_imports_kg", "gap_kg", "rule_summary"]
    ].copy()
    table_df["gap_pct"] = table_df["gap_pct"].map(format_pct)
    table_df["reported_exports_kg"] = table_df["reported_exports_kg"].map(format_kg)
    table_df["mirror_imports_kg"] = table_df["mirror_imports_kg"].map(format_kg)
    table_df["gap_kg"] = table_df["gap_kg"].map(format_kg)
    table_df = table_df.rename(
        columns={
            "country": "Country",
            "risk": "Risk",
            "gap_pct": "Gap %",
            "reported_exports_kg": "Reported exports",
            "mirror_imports_kg": "Mirror imports",
            "gap_kg": "Gap",
            "rule_summary": "Why flagged",
        }
    )
    st.dataframe(table_df, use_container_width=True, hide_index=True)
