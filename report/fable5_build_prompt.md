# Build Prompt for Fable 5 — Dealership Acquisition & Inventory Analytics App

## Mission

Build a working web application for a Toyota dealership's used-vehicle team that
replaces a manual spreadsheet/PDF workflow. Managers upload two kinds of files —
**sold-units exports** (a chosen trailing window: 30/60/90/120 days) and
**current-inventory exports** — and the app produces the same analysis as an
existing reference PDF report (attached/described below), but as a live,
filterable, persistent web dashboard with a PDF export button.

This is v1 for a single dealership. No login, no billing, no multi-tenant UI.
But design the database schema so a `dealership_id` scaffold exists cleanly —
this app is expected to eventually be handed to other dealerships as separate
deployments/tenants, so don't paint the data model into a single-store corner,
even though you won't build any tenant-switching UI now.

## Tech stack (locked — do not deviate)

- **Framework:** Next.js (App Router, TypeScript)
- **Database:** Supabase (Postgres)
- **Hosting:** Vercel
- **PDF generation:** a pure-JS/TS renderer (e.g. `@react-pdf/renderer`) — avoid
  headless-Chrome/Puppeteer approaches, they're brittle in Vercel's serverless
  environment.
- No auth provider needed for v1 (no login), but don't hardcode secrets/URLs —
  use environment variables the standard Next.js/Vercel way.

## Reference materials

A prior analysis of this exact dealership's data already exists in this repo at
`report/analyze.py` and `report/build_pdf.py` (branch with PR open). Treat those
as the **spec for exact formulas and report layout** — port the calculation
logic into TypeScript; do not shell out to Python at runtime. The existing
`report/Buyers_Report.pdf` is the visual/tonal reference for the PDF export:
navy (#0B2545) header bars, steel (#13315C) table headers, red (#C8102E) accent
for negative/urgent callouts, green for positive/fast-mover callouts, light-grey
zebra striping, a 5-bullet executive summary up top, KPI stat tiles, then one
section per report below.

## Source files this app must ingest

### File type 1 — Sold Units (a trailing N-day window: 30/60/90/120, user's choice)

Real column headers from this dealership's export (auto-detect these as the
default mapping; still show the mapping-wizard UI so other dealers' exports
with different headers can be matched manually):

```
Year, Make, Model, Front Gross, Back Gross, Vehicle Age, Source Type,
Retail Price, Mileage
```

Notes on this file's real-world quirks the app must handle:
- Row 1 (after header) is often a totals/summary row where every field is `"-"`
  except gross totals — detect and exclude rows where Year/Make/Model are `"-"`.
- Gross columns are formatted as currency strings (`"$1,234.56"`, sometimes
  negative like `"-$695.75"`) — parse to numeric, preserving sign.
- `Retail Price` can be blank or `"$0.00"` — treat as missing, not zero.
- `Vehicle Age` = days in inventory until sold (i.e., days-to-sell).
- `Source Type` values look like `"Trade In 1"` / `"Auction Or Wholesale"` /
  blank — useful as a **fallback** signal only (see classification rules below;
  the stock-number suffix is authoritative but this file has no stock number
  column today — if a future export adds one, wire it in; otherwise rely on
  `Source Type` text for this file type).
- A handful of rows are legitimate data-entry outliers (front gross beyond
  roughly ±$15k) — flag them as outliers in the UI (visually marked, filterable
  toggle "include data-quality outliers") rather than silently dropping them;
  exclude from averages by default but let a user opt them back in.
- Model names need light normalization to a base nameplate for grouping (e.g.
  `"Tacoma 4WD"` → `Tacoma`, `"Camry XSE"` → `Camry`, `"Grand Cherokee L"` →
  `Grand Cherokee`) — make/model casing should also be normalized
  (`"toyota"` → `Toyota`).

### File type 2 — Current Inventory (a point-in-time snapshot)

This is a wide export (~70 columns) from the dealer's inventory management
system. Only these matter for the app; ignore the rest but don't error on their
presence:

```
Age, Vehicle (e.g. "2024 Toyota Camry SE" — parse Year/Make/Model/Trim out of
this single string), Stock #, VIN, Odometer, Price, Cost, AskingPrice,
Appraiser, Appr. Salesperson, Reconditioning Cost
```

- `Vehicle` is a single free-text field like `"2025 Toyota 4Runner SR5"` —
  split into Year (first token), Make (second token), Model+Trim (remainder,
  with the same base-nameplate normalization as above, e.g. `"4Runner SR5"` →
  model `4Runner`, trim `SR5`).
- `Stock #` is the field that carries the acquisition-source suffix (see below)
  — this is the **authoritative** source signal for inventory-file rows.
- `Cost` is frequently blank for very new arrivals — treat as missing, not zero.

## Acquisition-source classification (critical business logic)

Source of truth is a **suffix on the Stock # field**, matched case-insensitively
against the trailing letters. Build this as a configurable rule table in the
database (`acquisition_source_rules`: `suffix TEXT`, `source_label TEXT`,
`note TEXT`), seeded with this dealership's exact legend, editable later from a
simple settings page (this is what makes the app portable to other dealers with
different suffix conventions):

| Suffix | Acquisition Source | Note |
|---|---|---|
| `S`  | Street Purchase | Bought directly from a private seller |
| `P`  | Auction | Auction or wholesale purchase |
| `A`  | Trade-In | Standard trade-in |
| `B`  | Trade-In | Standard trade-in (second trade code) |
| `PA` | Trade-In | Trade-in taken against a unit that was itself a prior auction purchase — classify as Trade-In for source rollups, but keep the raw suffix stored so this "auction-origin trade" chain is filterable/visible as a distinct tag in the UI. |

Matching rule: strip leading digits/letters that form the base stock number,
extract the trailing alphabetic suffix (check 2-letter suffixes like `PA`
before falling back to single-letter `P`/`A`/`B`/`S`). If no known suffix
matches, fall back to the `Source Type` text column (`starts with "Trade"` →
Trade-In, `starts with "Auction"` → Auction). If neither resolves, classify as
`Unknown` and flag for manual review in the UI (a manager should be able to
click a row and manually set its acquisition source).

## Data model (Supabase/Postgres — suggested shape, adjust as needed)

- `dealerships` — id, name (single seed row for now; future-proofing only)
- `datasets` — id, dealership_id, type (`sold_units` | `inventory`),
  window_days (30/60/90/120, null for inventory), period_label,
  uploaded_at, source_filename, raw_column_mapping (jsonb — stores the
  resolved column-mapping choices for audit/reuse)
- `sold_units` — dataset_id FK, year, make, model, trim, front_gross,
  back_gross, total_gross (generated), days_to_sell, retail_price, mileage,
  source_type_raw, acquisition_source (enum: trade/auction/street/unknown),
  acquisition_note, is_outlier (bool)
- `inventory_units` — dataset_id FK, year, make, model, trim, stock_number,
  vin, odometer, asking_price, cost, age_days, acquisition_source,
  acquisition_note, appraiser, salesperson
- `acquisition_source_rules` — suffix, source_label, note (seeded per table
  above, editable)

## Core calculations (port exactly from `report/analyze.py` / `build_pdf.py`)

For whichever sold-units dataset (window) is currently selected, plus the most
recent inventory snapshot:

1. **Velocity** — days-to-sell ranked; fast mover flag at `<21 days` (make this
   threshold configurable, default 21); fast-vs-slow comparison of avg
   front/back/total gross, mileage, model year, and acquisition-source mix;
   velocity by model/trim; days-to-sell by acquisition source.
2. **Gross Profit** — front/back/total gross per unit and as averages; average
   gross by model/trim/year-band/price-band; acquisition-source breakdown
   (front/back/total/days-to-sell per source, with the gross gap explicitly
   computed between sources); units beating the store average total gross;
   negative-front-gross deals with common-trait breakdown (by source, model,
   age, mileage).
   - Year bands and price bands should be **computed dynamically** from the
     dataset's actual distribution (e.g. quartile-based cut points), not
     hardcoded date ranges — this keeps the report correct as time passes and
     across different dealerships' inventory mixes.
3. **Inventory Health** — days supply per model = current units in stock ÷
   (sold-in-window ÷ window_days); status bands: `<30` thin/buy, `30–60`
   healthy, `60–90` heavy, `90+` overstocked, and a "no sales" / dead-stock
   status when daily rate is zero; sell-through rate = sold ÷ (sold + in
   stock); aged-unit flags for every in-stock unit over a configurable
   threshold (default 60 days) with model, age, asking price, cost,
   acquisition source, and total capital tied up.
4. **Buyer's Target List** — rank models that are simultaneously fast movers,
   above-average gross, and thin in current stock; for each, compute an ideal
   acquisition price range (median actual sold retail price for that model
   minus a target front-gross band) and the preferred acquisition source
   (whichever source produced better total gross for that model).
5. **Do Not Buy list** — slow movers, weak/negative gross, or overstocked
   models, calling out when a specific acquisition source is the driver of the
   losses (this dealership's real pattern: auction units of the same nameplate
   that's profitable on trade often lose money — surface this kind of
   source-vs-model interaction automatically, don't hardcode it to specific
   models).

## Interactive dashboard requirements

- **Snapshot/window picker** at the top: choose which sold-units dataset
  (30/60/90/120-day window, by upload date) and which inventory snapshot to
  view. Show a list of all historical uploads per type so past snapshots
  remain browsable (not just the latest).
- **Filters** (combinable, AND logic): Make/Model/Trim; Acquisition Source
  (trade/auction/street/unknown, multi-select); Price Band & Year Range;
  Days-to-Sell/Age Bucket (fast mover / slow mover / custom day threshold).
- **KPI summary cards**: units sold in window, avg total gross, avg days to
  sell, current inventory count, capital tied up in aged units — mirroring the
  reference PDF's executive-summary stat strip.
- **Tables** for each of the 5 report sections above, sortable by any column,
  reflecting whatever filters are currently active.
- A lightweight **trend view**: when 2+ historical snapshots of the same
  window-length exist, show simple before/after or line-chart comparison of
  headline metrics (avg total gross, avg days-to-sell, days supply) across
  upload dates.

## Upload flow / column-mapping wizard

1. User selects file type (Sold Units or Inventory) and, for Sold Units, the
   window length (30/60/90/120 days).
2. User uploads a CSV or XLS/XLSX file.
3. App parses headers and **auto-suggests** a column mapping using the known
   header names above as defaults (fuzzy/case-insensitive match).
4. User reviews/adjusts the mapping in a simple UI (dropdown per required
   field: Year, Make, Model, Front Gross, Back Gross, Days/Age, Source Type,
   Retail Price, Mileage, Stock #, VIN, Odometer, Cost, Asking Price, etc. —
   whichever apply to the file type) before committing the import.
5. On commit: parse rows, normalize currency/number formats, classify
   acquisition source per the suffix rules, flag outliers, store as a new
   `datasets` row plus its child rows, and redirect to the dashboard filtered
   to this new snapshot.

## PDF export

A button on the dashboard generates a PDF matching the structure and visual
style of `report/Buyers_Report.pdf`: cover header, 5-bullet executive summary
with KPI tiles, then the Velocity / Gross Profit / Inventory Health / Buyer's
Target List / Do Not Buy sections as clean tables with brief callout
commentary, using the current dashboard filters as the report's scope. Include
a short methodology footer noting the window length, snapshot dates, and any
excluded outliers — same spirit as the existing PDF's methodology section.

## Seed data

On first deploy, import this dealership's two real files as the very first
stored snapshot (30-day sold-units window + the current-inventory snapshot)
so the dashboard is populated and testable immediately — don't ship an empty
database requiring a first upload before anything is visible.

## Out of scope for v1 (do not build)

- Login/authentication of any kind
- Multi-dealership account switching, billing, or signup flows
- Any external DMS API integration (file upload only)

## Acceptance checklist

- [ ] Uploading the seed sold-units CSV and inventory XLS through the mapping
      wizard produces the same headline numbers as the reference PDF (store
      avg total gross ≈ $4,051, trade-vs-auction gross gap ≈ $1,088, etc. —
      exact figures may shift slightly with different outlier-handling toggles,
      but should be in the same neighborhood).
- [ ] Stock numbers ending in `S`, `P`, `A`, `B`, `PA` classify correctly as
      Street/Auction/Trade-In/Trade-In/Trade-In respectively.
- [ ] Dashboard filters combine correctly (e.g. Make=Toyota AND
      Source=Trade-In AND Age Bucket=Fast Mover returns the right subset).
- [ ] Switching the window picker between two different uploaded snapshots
      changes all report numbers accordingly.
- [ ] PDF export visually matches the reference report's tone (navy/steel/red
      palette, KPI tiles, section tables, executive summary).
- [ ] Aged-unit and days-supply calculations use the exact formulas specified
      above, not approximations.
