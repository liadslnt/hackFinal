from __future__ import annotations

import csv
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from trade_risk_analysis import build_mirror_dataset, default_output_path, save_dataset


PROJECT_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765

PRODUCT_PRESETS = {
    "253090": "Other mineral substances",
    "283691": "Lithium carbonate",
    "282520": "Lithium oxide and hydroxide",
    "850760": "Lithium-ion batteries",
}

SODIUM_FILE = PROJECT_DIR / "TradeData_4_22_2026_12_56_0.csv"


def json_response(handler: SimpleHTTPRequestHandler, payload: object, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: SimpleHTTPRequestHandler, message: str, status: int = 400) -> None:
    json_response(handler, {"error": message}, status=status)


def load_json_dataset(product_code: str, year: int) -> list[dict]:
    path = PROJECT_DIR / default_output_path(product_code, year)
    if not path.exists():
        raise FileNotFoundError(f"No cached dataset found for HS {product_code} in {year}.")

    raw = path.read_bytes()
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            return json.loads(raw.decode(encoding))
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Unable to decode dataset: {path.name}")


def list_cached_datasets() -> list[dict]:
    datasets: list[dict] = []
    pattern = re.compile(r"mirror_risk_(?P<hs>\d+)_(?P<year>\d{4})\.json$")

    for path in sorted(PROJECT_DIR.glob("mirror_risk_*.json")):
        match = pattern.match(path.name)
        if not match:
            continue
        hs = match.group("hs")
        year = int(match.group("year"))
        product = PRODUCT_PRESETS.get(hs, hs)
        try:
            records = load_json_dataset(hs, year)
            if records and isinstance(records[0], dict):
                product = str(records[0].get("product") or product)
        except Exception:
            records = []

        datasets.append(
            {
                "hs": hs,
                "year": year,
                "product": product,
                "label": f"{hs} · {PRODUCT_PRESETS.get(hs, product)} · {year}",
                "records": len(records),
            }
        )

    datasets.sort(key=lambda item: (item["hs"] != "283691", -item["year"], item["hs"]))
    return datasets


def normalize_records(records: list[dict]) -> list[dict]:
    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    def as_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    for record in records:
        for key in [
            "reported_exports_usd",
            "mirror_imports_usd",
            "gap_usd",
            "reported_exports_kg",
            "mirror_imports_kg",
            "gap_kg",
            "gap_pct",
        ]:
            record[key] = as_float(record.get(key))

    return sorted(
        records,
        key=lambda row: (
            risk_order.get(str(row.get("risk")), 99),
            -as_float(row.get("gap_pct")),
            str(row.get("country", "")),
        ),
    )


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_sodium_signal() -> dict | None:
    if not SODIUM_FILE.exists():
        return None

    raw = SODIUM_FILE.read_bytes()
    decoded = None
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        return None

    records = list(csv.DictReader(decoded.splitlines()))
    rows = []
    for row in records:
        if (
            row.get("reporterISO", "").strip() == "ARG"
            and row.get("flowDesc", "").strip().lower() == "import"
            and row.get("cmdCode", "").strip() == "283620"
            and str(row.get("refYear", "")).strip() == "2024"
        ):
            qty = safe_float(row.get("altQty")) or safe_float(row.get("netWgt")) or safe_float(row.get("qty"))
            rows.append(
                {
                    "month": int(safe_float(row.get("refMonth"))),
                    "partner": row.get("partnerDesc", "").strip() or row.get("partnerISO", "").strip(),
                    "partnerISO": row.get("partnerISO", "").strip(),
                    "quantity_kg": qty,
                }
            )

    world_rows = [row for row in rows if row["partnerISO"] == "W00"]
    supplier_rows = [row for row in rows if row["partnerISO"] != "W00"]
    if not world_rows:
        return None

    monthly = {}
    for row in world_rows:
        monthly[row["month"]] = monthly.get(row["month"], 0.0) + row["quantity_kg"]

    suppliers = {}
    for row in supplier_rows:
        suppliers[row["partner"]] = suppliers.get(row["partner"], 0.0) + row["quantity_kg"]

    monthly_rows = [
        {"month": month, "quantity_kg": quantity}
        for month, quantity in sorted(monthly.items())
    ]
    total = sum(monthly.values())
    peak = max(monthly_rows, key=lambda row: row["quantity_kg"])
    top_suppliers = [
        {
            "supplier": name,
            "quantity_kg": quantity,
            "share_pct": quantity / max(total, 1.0) * 100,
        }
        for name, quantity in sorted(suppliers.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    return {
        "total_kg": total,
        "peak_month": peak["month"],
        "peak_month_kg": peak["quantity_kg"],
        "monthly": monthly_rows,
        "top_suppliers": top_suppliers,
    }


class PremiumHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            self.path = "/premium_app.html"
            return super().do_GET()

        if parsed.path == "/api/datasets":
            return json_response(self, {"datasets": list_cached_datasets()})

        if parsed.path == "/api/risk":
            hs = query.get("hs", ["283691"])[0].strip()
            year = int(query.get("year", ["2024"])[0])
            try:
                records = normalize_records(load_json_dataset(hs, year))
            except Exception as exc:
                return error_response(self, str(exc), status=404)

            return json_response(
                self,
                {
                    "hs": hs,
                    "year": year,
                    "product": records[0].get("product", PRODUCT_PRESETS.get(hs, hs)) if records else hs,
                    "records": records,
                    "summary": {
                        "total": len(records),
                        "high": sum(1 for row in records if row.get("risk") == "HIGH"),
                        "medium": sum(1 for row in records if row.get("risk") == "MEDIUM"),
                        "low": sum(1 for row in records if row.get("risk") == "LOW"),
                    },
                },
            )

        if parsed.path == "/api/sodium":
            return json_response(self, {"signal": load_sodium_signal()})

        if parsed.path == "/api/build":
            hs = query.get("hs", ["283691"])[0].strip()
            year = int(query.get("year", ["2024"])[0])
            sleep_seconds = float(query.get("sleep", ["0.25"])[0])
            try:
                dataset = build_mirror_dataset(year=year, product_code=hs, sleep_seconds=sleep_seconds)
                save_dataset(dataset, default_output_path(hs, year))
                return json_response(self, {"ok": True, "records": len(dataset)})
            except Exception as exc:
                return error_response(self, str(exc), status=500)

        return super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), PremiumHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"OriginTrace premium app running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
