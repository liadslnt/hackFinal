# OriginTrace: Open-Source Supply Chain Risk Intelligence

OriginTrace is an investigation platform for critical-material supply chains. It uses open-source trade data to detect suspicious inconsistencies between what a country reports exporting and what the rest of the world reports importing from that same country.

The goal is not to claim fraud automatically. The goal is to turn fragmented public data into clear, prioritized investigation leads.

## Why This Matters

Critical supply chains are international, opaque, and fragmented. For materials such as lithium carbonate, lithium hydroxide, batteries, or even agricultural commodities like wheat, there is often no single source of truth.

Companies, regulators, insurers, auditors, and buyers need to answer questions such as:

- Does a country's reported export volume match what its trading partners report?
- Are there hidden volumes, reporting gaps, or possible origin inconsistencies?
- Is a trade anomaly large enough to matter physically, or is it just a small statistical artifact?
- Can the anomaly be explained by logistics constraints, customs friction, industrial inputs, or other public signals?

OriginTrace starts with public trade records and transforms them into an investigation workflow.

## What The App Does

The Streamlit app allows the user to choose:

- an HS product code
- a year
- a country

It then compares two views of the same flow:

- **Reported exports:** what the selected exporter says it exported.
- **Mirror imports:** what all partner countries say they imported from that exporter.

The app computes the physical gap in kilograms, the relative discrepancy, and a risk level:

- `LOW`
- `MEDIUM`
- `HIGH`

It also shows the partner-country flows behind the signal, so the user can inspect where the mismatch comes from.

## Open-Source Data Sources

The project is built around open and public data sources:

- **WITS / UN Comtrade public trade data:** used to reconstruct export and mirror-import flows by HS code, year, reporter, and partner.
- **Local Comtrade CSV extracts:** used as a fallback when public endpoints are incomplete or unstable for specific products.
- **World Bank Logistics Performance Index (LPI):** used as a structural logistics context layer for customs, infrastructure, international shipments, tracking, and timeliness.
- **UNCTAD maritime profile data:** used as country-level maritime and port context, including container throughput and shipping indicators.

All analysis is based on open-source or locally provided public datasets. No private APIs are required.

## Risk Logic

The risk score intentionally combines both relative and absolute discrepancy.

A very small country flow can have a huge percentage gap without being operationally meaningful. OriginTrace avoids over-penalizing small flows by considering volume thresholds in kilograms.

Core idea:

```text
gap_kg = abs(mirror_imports_kg - reported_exports_kg)
gap_pct = gap_kg / reported_exports_kg
```

The scoring model then applies volume-aware thresholds:

- Small flows are usually capped at low risk.
- Medium flows require both a meaningful percentage gap and a meaningful kilogram gap.
- Large flows can become high risk when the discrepancy is significant at industrial scale.

This makes the output more useful for real investigations, where a 90% gap on 20 kg should not be treated like a 36% gap on tens of millions of kilograms.

## Demo Case: Argentina Lithium Carbonate, 2024

The main demo case is:

```text
Country: Argentina
Product: Lithium carbonate
HS code: 283691
Year: 2024
```

In the cached dataset, Argentina is flagged as high risk because:

- Argentina reports around 48 million kg of lithium carbonate exports.
- Partner countries report around 65 million kg imported from Argentina.
- The resulting discrepancy is more than 17 million kg, around 36%.

The app includes a quarterly chart showing whether the discrepancy is stable, seasonal, or concentrated during specific periods.

## Explainability Layers

OriginTrace does not stop at the anomaly. It adds context to help investigators understand what to check next.

### Sodium Carbonate Input Check

For Argentina, the app includes a local Comtrade extract for sodium carbonate imports. Sodium carbonate is an important industrial input for lithium carbonate processing.

This layer helps answer:

- Is there evidence of upstream industrial activity?
- Does the processing input signal make the lithium carbonate export story more plausible?
- Does the trade anomaly remain unexplained even after adding input context?

### Structural Logistics Layer

The app also adds logistics context using public indicators:

- World Bank LPI rank and score
- customs performance
- infrastructure quality
- international shipment reliability
- tracking and tracing
- timeliness
- UNCTAD container throughput

This helps distinguish between:

- possible reporting friction
- customs or logistics constraints
- timing mismatches
- rerouting
- stronger origin-risk signals

## What's Next

OriginTrace currently starts from trade discrepancies and enriches them with logistics and input-context layers. The next step is to move from isolated material tracking to a more holistic verification engine that combines real industry data, chemistry, satellite observation, and operational signals.

### 1. Chemical Feasibility Layer

The most important next module is chemical validation.

For each target product, the system would map its required precursor materials and compare them with observed trade flows. For lithium carbonate, for example, this means checking whether upstream inputs such as sodium carbonate, lithium brines, lithium hydroxide, reagents, and processing chemicals are consistent with the claimed output.

The goal is simple:

```text
If the recipe does not add up, the claimed production is not physically plausible.
```

This would turn the platform from a trade-anomaly detector into a chemistry-aware supply-chain verification tool.

### 2. Satellite Verification

The second expansion is satellite-based physical verification.

Using sources such as Google Earth Engine, Sentinel, or Landsat datasets, the platform could observe production sites over time and detect physical changes such as:

- evaporation pond expansion
- new processing infrastructure
- increased road activity
- changes around mines, plants, and export hubs

This would allow the platform to correlate physical site activity with declared trade volumes.

If trade volumes increase sharply but the production site does not visibly expand or intensify, that becomes a stronger investigation signal.

### 3. Gap Identification Between Physical Reality And Trade Claims

The satellite layer would not be used as standalone proof. Instead, it would be compared with trade data.

The platform would ask:

- Does the site's physical footprint support the declared export volume?
- Did visible production capacity grow before or during the export increase?
- Are there discrepancies between physical reality and reported trade flows?

This would help highlight cases where the origin story breaks down.

### 4. Hiring And Capacity Signals

Another planned layer is hiring verification.

The platform could cross-reference employment growth with trade-volume claims by tracking public job postings, company pages, and hiring signals around operators, mines, processing plants, logistics companies, and customs brokers.

The logic is:

```text
If trade volumes spike but hiring and operational capacity remain flat, something does not add up.
```

Hiring signals would help distinguish between real industrial growth and unexplained trade-volume increases.

Together, these modules would make OriginTrace a modular verification platform:

```text
Trade data + chemical inputs + satellite reality + hiring signals = stronger supply-chain intelligence.
```

## Supported Products

The app includes presets for:

```text
253090 - Other mineral substances
283691 - Lithium carbonate
282520 - Lithium oxide and hydroxide
850760 - Lithium-ion batteries
1001   - Wheat and meslin
```

Additional HS codes can be added easily in `app.py`.

## Project Structure

```text
app.py
```

Main Streamlit application. Handles the user interface, country selection, risk display, partner flows, Argentina demo layers, and logistics context.

```text
trade_risk_analysis.py
```

Core data engine. Fetches or loads trade data, computes reported exports, mirror imports, gaps, reasons, and risk levels.

```text
argentina_monthly_chart.py
```

Builds the Argentina 2024 mirror-trade chart used in the demo.

```text
mirror_risk_<hs_code>_<year>.json
```

Cached analysis outputs. These allow the app to load quickly without re-fetching all trade data every time.

```text
TradeData_*.csv
```

Local Comtrade CSV extracts used for specific evidence layers or fallback data.

```text
requirements.txt
```

Python dependencies.

## Running The App

From the project folder:

```powershell
cd C:\Users\liad\Documents\hackaton
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

If you use the local Python installation from this machine:

```powershell
& "C:\Users\liad\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run "C:\Users\liad\Documents\hackaton\app.py"
```

## Command-Line Dataset Generation

You can also generate a dataset directly:

```powershell
python trade_risk_analysis.py --product-code 283691 --year 2024
```

This creates a cached file such as:

```text
mirror_risk_283691_2024.json
```

The app can then load the cached dataset instantly.

## Design Principles

OriginTrace is designed around four principles:

- **Open-source first:** rely on public trade and logistics data.
- **Investigation, not accusation:** a high score is a lead, not proof of wrongdoing.
- **Volume-aware scoring:** prioritize discrepancies that matter physically.
- **Modular expansion:** add new evidence layers such as satellite imagery, job postings, port events, customs records, or company disclosures.

## Limitations

Trade data is imperfect. Discrepancies may come from:

- timing differences
- reporting delays
- partner misclassification
- re-exports
- different customs procedures
- missing quantities
- incomplete public endpoints

For this reason, OriginTrace should be interpreted as a triage and investigation tool, not a final compliance verdict.

## Vision

The long-term vision is to build a modular risk-intelligence platform for supply chains.

The current prototype starts with trade anomalies. Future modules can add:

- satellite activity near mines and processing sites
- shipping and vessel movement signals
- port disruption and accident monitoring
- hiring and company expansion signals
- customs-origin consistency checks
- ESG and forced-labor risk indicators

In short:

```text
OriginTrace turns trade anomalies into actionable supply-chain investigations.
```
