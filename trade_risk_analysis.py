from __future__ import annotations

import argparse
import csv
import json
import re
from html import unescape
from pathlib import Path
from time import sleep

import pandas as pd
import requests

DEFAULT_PRODUCT_CODE = "283691"
DEFAULT_YEAR = 2024
COMTRADE_LOCAL_BATTERY_FILE = "TradeData_4_22_2026_11_18_29.csv"

WITS_EXPORT_OVERVIEW_URL = (
    "https://wits.worldbank.org/trade/comtrade/en/country/ALL/year/{year}/"
    "tradeflow/Exports/partner/WLD/product/{product_code}"
)
WITS_EXPORT_DETAIL_URL = (
    "https://wits.worldbank.org/trade/comtrade/en/country/{reporter_code}/year/{year}/"
    "tradeflow/Exports/partner/ALL/product/{product_code}"
)
WITS_MIRROR_IMPORT_URL = (
    "https://wits.worldbank.org/trade/comtrade/en/country/All/year/{year}/"
    "tradeflow/Imports/partner/{reporter_code}/product/{product_code}"
)

BLACKLIST_CODES = {"ALL", "EUN", "OAS", "WLD"}
BLACKLIST_NAMES = {"World", "European Union"}


def default_output_path(product_code: str, year: int) -> str:
    return f"mirror_risk_{product_code}_{year}.json"


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_wits_table(html: str) -> list[dict]:
    table_match = re.search(
        r"<table[^>]*id='dataCatalogMetadata'[^>]*>(?P<table>.*?)</table>",
        html,
        flags=re.S,
    )
    if not table_match:
        return []

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group("table"), flags=re.S)
    parsed_rows: list[dict] = []

    for row_html in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S)
        if len(cells) < 7:
            continue

        reporter = strip_html(cells[0])
        flow = strip_html(cells[1])
        product_code = strip_html(cells[2])
        product = strip_html(cells[3])
        year = strip_html(cells[4])
        partner = strip_html(cells[5])
        value_text = strip_html(cells[6])
        quantity_text = strip_html(cells[7]) if len(cells) > 7 else ""
        quantity_unit = strip_html(cells[8]) if len(cells) > 8 else ""

        if reporter == "Reporter" or flow == "TradeFlow" or value_text == "Trade Value 1000USD":
            continue

        value_kusd = float(value_text.replace(",", "")) if value_text else 0.0
        parsed_rows.append(
            {
                "reporter": reporter,
                "flow": flow,
                "product_code": product_code,
                "product": product,
                "year": year,
                "partner": partner,
                "value_kusd": value_kusd,
                "quantity": float(quantity_text.replace(",", "")) if quantity_text else 0.0,
                "quantity_unit": quantity_unit,
            }
        )

    return parsed_rows


def fetch_text(session: requests.Session, url: str, timeout: int = 30) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
    )
    return session


def extract_product_name_from_html(html: str, fallback: str | None = None) -> str:
    title_match = re.search(r"<title>\s*(.*?)\s*\|", html, flags=re.S | re.I)
    if title_match:
        title_value = strip_html(title_match.group(1))
        if title_value and title_value != "WITS - Error":
            return title_value

    rows = parse_wits_table(html)
    if rows:
        product = rows[0].get("product", "").strip()
        if product:
            return product

    return fallback or "Unknown product"


def fetch_country_index(
    session: requests.Session,
    year: int = DEFAULT_YEAR,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> tuple[list[dict], str]:
    url = WITS_EXPORT_OVERVIEW_URL.format(year=year, product_code=product_code)
    html = fetch_text(session, url)
    product_name = extract_product_name_from_html(html, fallback=product_code)

    if "WITS - Error" in html:
        raise ValueError(
            f"WITS public page returned an error for product code {product_code} in year {year}. "
            "This code/year may not be publicly available through this endpoint."
        )

    matches = re.findall(
        rf"country/(?P<code>[A-Z]{{3}})/year/{year}/tradeflow/Exports/partner/ALL/product/{product_code}'>(?P<name>[^<]+)</a>",
        html,
    )

    countries = []
    seen_codes: set[str] = set()
    for code, name in matches:
        if code in BLACKLIST_CODES or code in seen_codes:
            continue
        seen_codes.add(code)
        countries.append({"reporter_code": code, "country": name})

    if not countries:
        raise ValueError(
            f"No exporter countries were found for product code {product_code} in year {year}. "
            "The product may be unavailable on the public WITS endpoint for that year."
        )

    return countries, product_name


def assign_mirror_risk(reported_exports_kg: float, mirror_imports_kg: float) -> tuple[str, list[str], float, str]:
    gap_kg = abs(mirror_imports_kg - reported_exports_kg)
    gap_ratio = gap_kg / max(reported_exports_kg, 1.0)

    if mirror_imports_kg > reported_exports_kg:
        direction = "mirror_above_reported"
        reason = f"mirror imports are {gap_ratio * 100:.1f}% above reported exports"
    elif mirror_imports_kg < reported_exports_kg:
        direction = "mirror_below_reported"
        reason = f"mirror imports are {gap_ratio * 100:.1f}% below reported exports"
    else:
        direction = "match"
        reason = "reported exports and mirror imports are close"

    # Normalize the signal by both relative gap and physical scale.
    # This avoids over-penalizing tiny trade flows with huge percentages.
    if reported_exports_kg < 100_000:
        return (
            "LOW",
            [
                "very small export volume",
                f"reported exports = {reported_exports_kg:,.0f} kg, below 100,000 kg floor",
            ],
            gap_ratio,
            direction,
        )

    if reported_exports_kg < 500_000:
        if gap_kg >= 250_000 and gap_ratio >= 1.00:
            return (
                "MEDIUM",
                [
                    reason,
                    f"gap = {gap_kg:,.0f} kg and exports = {reported_exports_kg:,.0f} kg",
                    "small exporter, so risk is capped by volume",
                ],
                gap_ratio,
                direction,
            )
        return (
            "LOW",
            [
                "small export volume",
                f"reported exports = {reported_exports_kg:,.0f} kg, below 500,000 kg",
            ],
            gap_ratio,
            direction,
        )

    if reported_exports_kg < 5_000_000:
        if gap_kg >= 1_000_000 and gap_ratio >= 0.50:
            return (
                "HIGH",
                [
                    reason,
                    f"gap = {gap_kg:,.0f} kg, threshold >= 1,000,000 kg and >= 50%",
                ],
                gap_ratio,
                direction,
            )
        if gap_kg >= 500_000 and gap_ratio >= 0.20:
            return (
                "MEDIUM",
                [
                    reason,
                    f"gap = {gap_kg:,.0f} kg, threshold >= 500,000 kg and >= 20%",
                ],
                gap_ratio,
                direction,
            )
        return (
            "LOW",
            [
                "reported exports and mirror imports are close at this scale",
                f"gap = {gap_kg:,.0f} kg and gap % = {gap_ratio * 100:.2f}%",
            ],
            gap_ratio,
            direction,
        )

    if gap_kg >= 2_000_000 and gap_ratio >= 0.30:
        return (
            "HIGH",
            [
                reason,
                f"gap = {gap_kg:,.0f} kg, threshold >= 2,000,000 kg and >= 30%",
            ],
            gap_ratio,
            direction,
        )
    if gap_kg >= 500_000 and gap_ratio >= 0.10:
        return (
            "MEDIUM",
            [
                reason,
                f"gap = {gap_kg:,.0f} kg, threshold >= 500,000 kg and >= 10%",
            ],
            gap_ratio,
            direction,
        )
    return (
        "LOW",
        [
            "reported exports and mirror imports are close",
            f"gap = {gap_kg:,.0f} kg and gap % = {gap_ratio * 100:.2f}%",
        ],
        gap_ratio,
        direction,
    )


def compute_country_mirror_entry(
    session: requests.Session,
    reporter_code: str,
    country_name: str,
    year: int,
    product_code: str,
    product_name: str,
) -> dict:
    export_url = WITS_EXPORT_DETAIL_URL.format(
        reporter_code=reporter_code,
        year=year,
        product_code=product_code,
    )
    mirror_url = WITS_MIRROR_IMPORT_URL.format(
        reporter_code=reporter_code,
        year=year,
        product_code=product_code,
    )

    export_html = fetch_text(session, export_url)
    mirror_html = fetch_text(session, mirror_url)
    export_rows = parse_wits_table(export_html)
    mirror_rows = parse_wits_table(mirror_html)

    world_row = next((row for row in export_rows if row["partner"] == "World"), None)
    reported_exports_usd = (world_row["value_kusd"] if world_row else 0.0) * 1000
    reported_exports_kg = world_row["quantity"] if world_row else 0.0

    mirror_imports_usd = (
        sum(row["value_kusd"] for row in mirror_rows if row["reporter"] not in BLACKLIST_NAMES) * 1000
    )
    mirror_imports_kg = sum(row["quantity"] for row in mirror_rows if row["reporter"] not in BLACKLIST_NAMES)

    risk, reasons, gap_ratio, direction = assign_mirror_risk(reported_exports_kg, mirror_imports_kg)
    gap_usd = abs(mirror_imports_usd - reported_exports_usd)
    gap_kg = abs(mirror_imports_kg - reported_exports_kg)

    top_export_partners = sorted(
        [
            {"country": row["partner"], "value_usd": round(row["value_kusd"] * 1000, 2)}
            for row in export_rows
            if row["partner"] not in BLACKLIST_NAMES
        ],
        key=lambda item: item["value_usd"],
        reverse=True,
    )[:5]

    top_mirror_importers = sorted(
        [
            {"country": row["reporter"], "value_usd": round(row["value_kusd"] * 1000, 2)}
            for row in mirror_rows
            if row["reporter"] not in BLACKLIST_NAMES
        ],
        key=lambda item: item["value_usd"],
        reverse=True,
    )[:5]

    return {
        "country": country_name,
        "reporter_code": reporter_code,
        "year": year,
        "product_code": product_code,
        "product": product_name,
        "reported_exports_usd": round(reported_exports_usd, 2),
        "mirror_imports_usd": round(mirror_imports_usd, 2),
        "gap_usd": round(gap_usd, 2),
        "reported_exports_kg": round(reported_exports_kg, 2),
        "mirror_imports_kg": round(mirror_imports_kg, 2),
        "gap_kg": round(gap_kg, 2),
        "gap_pct": round(gap_ratio * 100, 2),
        "direction": direction,
        "risk": risk,
        "reasons": reasons,
        "rule_summary": (
            f"reported exports = {reported_exports_kg:,.0f} kg, "
            f"mirror imports = {mirror_imports_kg:,.0f} kg, "
            f"gap = {gap_kg:,.0f} kg ({gap_ratio * 100:.2f}%)"
        ),
        "top_export_partners": top_export_partners,
        "top_mirror_importers": top_mirror_importers,
        "export_page": export_url,
        "mirror_page": mirror_url,
    }


def build_mirror_dataset(
    year: int = DEFAULT_YEAR,
    product_code: str = DEFAULT_PRODUCT_CODE,
    sleep_seconds: float = 0.25,
) -> list[dict]:
    if str(product_code) == "850760":
        csv_path = Path(COMTRADE_LOCAL_BATTERY_FILE)
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Missing local Comtrade battery file: {csv_path}. "
                "Place the downloaded 850760 CSV in the project folder."
            )
        return build_mirror_dataset_from_comtrade_csv(
            csv_path=csv_path,
            year=year,
            product_code=product_code,
        )

    session = build_session()
    countries, product_name = fetch_country_index(session, year=year, product_code=product_code)
    dataset: list[dict] = []

    for country in countries:
        dataset.append(
            compute_country_mirror_entry(
                session=session,
                reporter_code=country["reporter_code"],
                country_name=country["country"],
                year=year,
                product_code=product_code,
                product_name=product_name,
            )
        )
        sleep(sleep_seconds)

    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    dataset.sort(key=lambda item: (risk_order.get(item["risk"], 99), -item["gap_pct"], item["country"]))
    return dataset


def load_dataset(path: str | Path) -> list[dict]:
    raw_bytes = Path(path).read_bytes()
    decoded_text = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            decoded_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        raise UnicodeDecodeError(
            str(path),
            raw_bytes,
            0,
            1,
            "Unable to decode dataset with utf-8, utf-8-sig, cp1252, or latin-1",
        )

    return json.loads(decoded_text)


def save_dataset(dataset: list[dict], output_path: str | Path) -> None:
    path = Path(output_path)
    path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")


def read_csv_with_fallback(path: str | Path, **kwargs) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise ValueError(f"Unable to read CSV file: {path}")


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
        raise UnicodeDecodeError(
            str(path),
            raw_bytes,
            0,
            1,
            "Unable to decode CSV with utf-8, utf-8-sig, cp1252, or latin-1",
        )

    reader = csv.DictReader(decoded_text.splitlines())
    return list(reader)


def build_mirror_dataset_from_comtrade_csv(
    csv_path: str | Path,
    year: int,
    product_code: str,
) -> list[dict]:
    df = pd.DataFrame(read_csv_records_with_fallback(csv_path))
    df = df.fillna("")

    # Normalize key string columns to avoid hidden spaces/BOM-style issues.
    for col in [
        "cmdCode",
        "refYear",
        "flowDesc",
        "reporterISO",
        "reporterDesc",
        "partnerISO",
        "partnerDesc",
        "cmdDesc",
        "altQtyUnitAbbr",
    ]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    available_codes = sorted(df["cmdCode"].dropna().astype(str).unique().tolist()) if "cmdCode" in df.columns else []
    available_years = sorted(df["refYear"].dropna().astype(str).unique().tolist()) if "refYear" in df.columns else []

    df = df[
        (df["cmdCode"].astype(str) == str(product_code))
        & (df["refYear"].astype(str) == str(year))
        & (df["flowDesc"].isin(["Import", "Export"]))
    ].copy()

    if df.empty:
        raise ValueError(
            f"No Comtrade CSV rows found for HS {product_code} in {year}. "
            f"Available years in file: {available_years[:10]}. "
            f"Available product codes in file include: {available_codes[:10]}."
        )

    for col in ["primaryValue", "altQty", "netWgt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["quantity_kg"] = 0.0
    if "altQtyUnitAbbr" in df.columns:
        alt_mask = df["altQtyUnitAbbr"].astype(str).str.lower().eq("kg")
        df.loc[alt_mask, "quantity_kg"] = df.loc[alt_mask, "altQty"]
    if "netWgt" in df.columns:
        zero_mask = df["quantity_kg"].eq(0.0)
        df.loc[zero_mask, "quantity_kg"] = df.loc[zero_mask, "netWgt"]

    product_name = df["cmdDesc"].iloc[0]
    reporters = sorted(df["reporterISO"].unique().tolist())
    dataset: list[dict] = []

    for reporter_iso in reporters:
        reporter_rows = df[df["reporterISO"] == reporter_iso].copy()
        country_name = reporter_rows["reporterDesc"].iloc[0]

        export_world = reporter_rows[
            (reporter_rows["flowDesc"] == "Export") & (reporter_rows["partnerISO"] == "W00")
        ]
        reported_exports_kg = float(export_world["quantity_kg"].sum())
        reported_exports_usd = float(export_world["primaryValue"].sum())

        mirror_rows = df[
            (df["flowDesc"] == "Import")
            & (df["partnerISO"] == reporter_iso)
            & (df["reporterISO"] != reporter_iso)
            & (df["reporterISO"] != "W00")
        ].copy()

        mirror_imports_kg = float(mirror_rows["quantity_kg"].sum())
        mirror_imports_usd = float(mirror_rows["primaryValue"].sum())

        risk, reasons, gap_ratio, direction = assign_mirror_risk(reported_exports_kg, mirror_imports_kg)
        gap_kg = abs(mirror_imports_kg - reported_exports_kg)
        gap_usd = abs(mirror_imports_usd - reported_exports_usd)

        top_export_partners_df = reporter_rows[
            (reporter_rows["flowDesc"] == "Export")
            & (reporter_rows["partnerISO"] != "W00")
        ].copy()
        top_export_partners = (
            top_export_partners_df.groupby("partnerDesc", dropna=False)["quantity_kg"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        top_export_partners_list = [
            {"country": idx, "value_usd": round(float(value), 2)} for idx, value in top_export_partners.items()
        ]

        top_mirror_importers = (
            mirror_rows.groupby("reporterDesc", dropna=False)["quantity_kg"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        top_mirror_importers_list = [
            {"country": idx, "value_usd": round(float(value), 2)} for idx, value in top_mirror_importers.items()
        ]

        dataset.append(
            {
                "country": country_name,
                "reporter_code": reporter_iso,
                "year": year,
                "product_code": product_code,
                "product": product_name,
                "reported_exports_usd": round(reported_exports_usd, 2),
                "mirror_imports_usd": round(mirror_imports_usd, 2),
                "gap_usd": round(gap_usd, 2),
                "reported_exports_kg": round(reported_exports_kg, 2),
                "mirror_imports_kg": round(mirror_imports_kg, 2),
                "gap_kg": round(gap_kg, 2),
                "gap_pct": round(gap_ratio * 100, 2),
                "direction": direction,
                "risk": risk,
                "reasons": reasons,
                "rule_summary": (
                    f"reported exports = {reported_exports_kg:,.0f} kg, "
                    f"mirror imports = {mirror_imports_kg:,.0f} kg, "
                    f"gap = {gap_kg:,.0f} kg ({gap_ratio * 100:.2f}%)"
                ),
                "top_export_partners": top_export_partners_list,
                "top_mirror_importers": top_mirror_importers_list,
                "export_page": f"local-comtrade-csv://{Path(csv_path).name}",
                "mirror_page": f"local-comtrade-csv://{Path(csv_path).name}",
            }
        )

    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    dataset.sort(key=lambda item: (risk_order.get(item["risk"], 99), -item["gap_pct"], item["country"]))
    return dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch official public WITS/Comtrade pages and compute mirror-gap risk by exporter country."
    )
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--product-code", default=DEFAULT_PRODUCT_CODE)
    parser.add_argument("--output", default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or default_output_path(args.product_code, args.year)
    dataset = build_mirror_dataset(
        year=args.year,
        product_code=args.product_code,
        sleep_seconds=args.sleep_seconds,
    )
    save_dataset(dataset, output_path)

    print(f"Saved mirror dataset to {Path(output_path).resolve()}")
    print()
    for row in dataset[:15]:
        print(
            f"{row['country']}: risk={row['risk']}, gap_pct={row['gap_pct']:.2f}, "
            f"reported_exports_usd={row['reported_exports_usd']:.0f}, "
            f"mirror_imports_usd={row['mirror_imports_usd']:.0f}"
        )


if __name__ == "__main__":
    main()
