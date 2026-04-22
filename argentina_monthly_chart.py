from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ALL_CARBONATE_2024_FILE = "TradeData_4_22_2026_12_19_27.csv"
OUTPUT_FILE = "argentina_mirror_trade_quarterly_2024.png"


def read_csv_records_with_fallback(path: str | Path) -> list[dict]:
    raw_bytes = Path(path).read_bytes()
    decoded_text = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            decoded_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        raise ValueError(f"Unable to decode CSV file: {path}")

    reader = csv.DictReader(decoded_text.splitlines())
    return list(reader)


def read_trade_csv(path: str | Path) -> pd.DataFrame:
    df = pd.DataFrame(read_csv_records_with_fallback(path)).fillna("")

    for col in ["freqCode", "flowDesc", "partnerISO", "reporterISO", "cmdCode", "refYear"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    for col in ["refMonth", "qty", "altQty", "netWgt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["quantity_kg"] = 0.0
    if "altQty" in df.columns:
        alt_mask = df["altQty"].gt(0)
        df.loc[alt_mask, "quantity_kg"] = df.loc[alt_mask, "altQty"]
    if "netWgt" in df.columns:
        zero_mask = df["quantity_kg"].eq(0.0)
        df.loc[zero_mask, "quantity_kg"] = df.loc[zero_mask, "netWgt"]

    return df


def build_monthly_series() -> pd.DataFrame:
    df = read_trade_csv(ALL_CARBONATE_2024_FILE)
    df = df[
        (df["freqCode"] == "M")
        & (df["cmdCode"] == "283691")
        & (df["refYear"] == "2024")
    ].copy()

    exports = df[
        (df["flowDesc"] == "Export")
        & (df["reporterISO"] == "ARG")
        & (df["partnerISO"] == "W00")
    ][["refMonth", "quantity_kg"]].copy()
    exports = exports.groupby("refMonth", as_index=False)["quantity_kg"].sum().rename(
        columns={"quantity_kg": "argentina_exports_kg"}
    )

    mirror_imports = df[
        (df["flowDesc"] == "Import")
        & (df["partnerISO"] == "ARG")
        & (df["reporterISO"] != "ARG")
    ][["refMonth", "quantity_kg"]].copy()
    mirror_imports = mirror_imports.groupby("refMonth", as_index=False)["quantity_kg"].sum().rename(
        columns={"quantity_kg": "world_imports_from_argentina_kg"}
    )

    months = pd.DataFrame({"refMonth": list(range(1, 13))})
    merged = months.merge(exports, on="refMonth", how="left").merge(mirror_imports, on="refMonth", how="left")
    merged = merged.fillna(0.0)
    merged["gap_kg"] = (
        merged["world_imports_from_argentina_kg"] - merged["argentina_exports_kg"]
    ).abs()
    return merged


def month_to_quarter(month: int) -> str:
    if month in [1, 2, 3]:
        return "Q1"
    if month in [4, 5, 6]:
        return "Q2"
    if month in [7, 8, 9]:
        return "Q3"
    return "Q4"


def build_quarterly_series(monthly: pd.DataFrame) -> pd.DataFrame:
    quarterly = monthly.copy()
    quarterly["quarter"] = quarterly["refMonth"].astype(int).map(month_to_quarter)

    def non_zero_mean(series: pd.Series) -> float:
        filtered = series[series > 0]
        if filtered.empty:
            return 0.0
        return float(filtered.mean())

    grouped = (
        quarterly.groupby("quarter", as_index=False)
        .agg(
            argentina_exports_kg=("argentina_exports_kg", non_zero_mean),
            world_imports_from_argentina_kg=("world_imports_from_argentina_kg", non_zero_mean),
            gap_kg=("gap_kg", non_zero_mean),
        )
    )

    quarter_order = ["Q1", "Q2", "Q3", "Q4"]
    grouped["quarter"] = pd.Categorical(grouped["quarter"], categories=quarter_order, ordered=True)
    grouped = grouped.sort_values("quarter").reset_index(drop=True)
    return grouped


def build_chart() -> Path:
    monthly = build_monthly_series()
    quarterly = build_quarterly_series(monthly)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1.5]},
    )

    x_labels = quarterly["quarter"].astype(str).tolist()

    ax1.plot(
        x_labels,
        quarterly["argentina_exports_kg"],
        marker="o",
        linewidth=2.8,
        label="Argentina reported exports (quarterly avg)",
        color="#0b3d91",
    )
    ax1.plot(
        x_labels,
        quarterly["world_imports_from_argentina_kg"],
        marker="o",
        linewidth=2.8,
        linestyle="--",
        label="World mirror imports from Argentina (quarterly avg)",
        color="#d62728",
    )
    ax1.fill_between(
        x_labels,
        quarterly["argentina_exports_kg"],
        quarterly["world_imports_from_argentina_kg"],
        color="#ffb3b3",
        alpha=0.25,
    )

    ax1.set_title("Argentina Lithium Carbonate Mirror Trade Gap in 2024", fontsize=16, weight="bold")
    ax1.set_ylabel("Quantity (kg)")
    ax1.legend()
    ax1.ticklabel_format(style="plain", axis="y")

    ax2.bar(
        x_labels,
        quarterly["gap_kg"],
        color="#6c757d",
        alpha=0.85,
        width=0.7,
    )
    ax2.set_xlabel("Quarter")
    ax2.set_ylabel("Absolute gap (kg)")
    ax2.ticklabel_format(style="plain", axis="y")

    note = (
        "HS 283691 | 2024 only | Source: local Comtrade monthly CSV for all carbonate trade\n"
        "Quarter values are averaged over non-zero months only, so missing months do not pull the average down."
    )
    fig.text(0.01, 0.01, note, fontsize=10)

    output_path = Path(OUTPUT_FILE)
    plt.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
    return output_path


if __name__ == "__main__":
    output = build_chart()
    print(f"Saved chart to {output.resolve()}")
