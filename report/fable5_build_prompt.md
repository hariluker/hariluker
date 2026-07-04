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
system. These matter for the app; ignore the rest but don't error on their
presence:

```
Age, Vehicle (e.g. "2024 Toyota Camry SE" — parse Year/Make/Model/Trim out of
this single string), Stock #, VIN, Odometer, Price, Cost, AskingPrice,
Appraiser, Appr. Salesperson, Reconditioning Cost
```

Plus, **optionally** (present in this dealer's export, but not guaranteed in
others — parse when present, gracefully omit the resulting UI/report elements
when absent, never error on their absence):

```
AutoTrader.com List Price, AutoTrader.com SRP, AutoTrader.com VDP,
AutoTrader.com % VDP, Cars.com List Price, Cars.com SRP, Cars.com VDP,
Cars.com % VDP, CarGurus List Price, CarGurus SRP, CarGurus VDP,
CarGurus % VDP, nVision Prob.toSell
```

- `Vehicle` is a single free-text field like `"2025 Toyota 4Runner SR5"` —
  split into Year (first token), Make (second token), Model+Trim (remainder,
  with the same base-nameplate normalization as above, e.g. `"4Runner SR5"` →
  model `4Runner`, trim `SR5`).
- `Stock #` is the field that carries the acquisition-source suffix (see below)
  — this is the **authoritative** source signal for inventory-file rows.
- `Cost` is frequently blank for very new arrivals — treat as missing, not zero.
- The optional market-demand fields (SRP = search-results-page impressions,
  VDP = vehicle-detail-page clicks, %VDP = click-through rate, nVision
  Prob.toSell = a third-party probability-to-sell score) are **leading**
  indicators of market interest, unlike everything else in this app which is
  backward-looking (what already sold). Store them on `inventory_units` as
  nullable fields. Surface a simple "Market Interest" indicator (e.g. derived
  from %VDP and/or nVision score, bucketed High/Medium/Low) in the Inventory
  Health section and as a secondary signal on the Buyer's Target List — e.g.
  flag "thin stock + high market interest" as a stronger buy signal than thin
  stock alone, and flag "healthy stock + low market interest" as an early
  warning that demand may be softening before it shows up in sales data.

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
  acquisition_note, appraiser, salesperson, market_list_price (nullable, best
  available of AutoTrader/Cars.com/CarGurus), market_vdp_pct (nullable),
  market_prob_to_sell (nullable), market_interest_bucket (nullable,
  High/Medium/Low derived from the above)
- `settings` — single-row config table: `fast_mover_days` (default 21),
  `aged_unit_days` (default 60), `flat_recon_cost` (default 1600, USD, one
  store-wide number, not per-unit/per-model — see Buyer's Target List below)
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
4. **Buyer's Target List** — this is the highest-stakes output in the app, so
   get the ranking metric right:
   - **Primary rank: total gross ÷ days-to-sell** (a capital-velocity metric,
     not raw average gross). A car that grosses less but turns faster recycles
     floorplan capital more times per month, which is what actually compounds
     into more monthly units sold — that's the real growth lever, not just
     fat single-unit checks. Still filter candidates to require thin current
     stock (see Inventory Health bands) so the list stays a genuine buy
     signal, not just "whatever turns fastest regardless of supply."
   - **Show front gross and back gross broken out separately** next to the
     ranking, not just blended into the total. Back gross is largely a
     function of F&I execution and the specific buyer's financing/warranty
     attach on that deal, not the vehicle itself — a model can rank well
     because of one lucky F&I-heavy deal. Surfacing the split lets a manager
     see whether a model's ranking is a real vehicle-level signal (strong
     front gross) or an F&I artifact (gross carried mostly by back-end),
     without hiding that distinction inside one blended number.
   - **Flag low-sample-size models** (fewer than 5 sold units in the selected
     window) as "directional, low sample" rather than a confident
     recommendation — a model with n=2-3 units can look like a great or
     terrible buy purely from one outlier deal; don't let the UI present that
     with the same confidence as a model with n=15+.
   - **Ideal acquisition price** = median actual sold retail price for that
     model in the current window − target front-gross band − a single flat
     store-wide recon-cost assumption (`settings.flat_recon_cost`, default
     $1,600 — this dealership doesn't want per-unit or per-model recon detail,
     just one constant subtracted uniformly; make it editable in settings, not
     hardcoded, since other dealers will have a different average).
   - **Preferred acquisition source** = whichever source produced better total
     gross ÷ days-to-sell for that model (consistent with the primary rank
     above), not just better raw gross.
   - Where the optional market-interest fields are present (see Inventory
     File §2), factor them in as a secondary flag: thin stock + high market
     interest strengthens the buy signal; healthy/heavy stock + low market
     interest is a soft early-warning that demand may be cooling before it
     shows up in sales history.
   - **Do not let this list recommend blanket avoidance of an otherwise
     strong-selling nameplate just because one acquisition source lost money
     on it** (see Do Not Buy below) — that's frequently a bid-discipline
     problem on a specific source, not a demand problem on the model.
5. **Do Not Buy list** — slow movers, weak/negative gross, or overstocked
   models, calling out when a specific acquisition source is the driver of the
   losses (this dealership's real pattern: auction units of the same nameplate
   that's profitable on trade often lose money — surface this kind of
   source-vs-model interaction automatically, don't hardcode it to specific
   models). **Important nuance:** when a model is profitable overall (e.g. via
   trade) but loses money specifically through one acquisition source (e.g.
   auction), the correct recommendation is "cap the max bid / stop overpaying
   via [source]," not "stop buying this model" — a source-specific
   overpayment problem is a bid-discipline fix, not a demand problem, and
   blanket-avoiding an otherwise strong nameplate would cost real inventory.
   Only recommend full avoidance when the model is weak across *all* sources.

### Known limitations to surface in the UI, not hide

- **Survivorship bias**: this app only ever sees units the store decided to
  retail. A trade appraised so poorly it was immediately wholesaled never
  appears in sold-units data as a bad trade — it just doesn't exist in the
  dataset. Add a one-line disclaimer on the Gross Profit and Buyer's Target
  List views: recommendations reflect retailed units only, not the full
  universe of trades/auction units considered.
- **Small samples**: as noted above, flag any model-level stat built from
  fewer than 5 units as low-confidence in the UI (e.g. a muted badge or
  asterisk), everywhere it appears — Velocity, Gross Profit, and the Buyer's
  Target List alike.

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
  - **Overlapping-window dedup**: a 30-day and a 90-day upload from the same
    week will share ~30 days of the same units. Any view that aggregates
    "across all snapshots" (rather than viewing one snapshot at a time) must
    dedup by VIN/stock-number + sale date before summing — otherwise volume
    and averages silently inflate. If true dedup is too complex for v1, it's
    acceptable to simply *not* offer an "all-time combined" aggregate view at
    all and only ever show one selected snapshot at a time — just don't ship
    a naive sum-across-snapshots view, it will produce wrong numbers.

## Live Acquisition Lookup (mobile-friendly, keep this simple)

A single lightweight page, not a new subsystem — this must reuse the exact
same aggregates already computed for the Buyer's Target List, not introduce
new calculation logic or any live/external data feed (no real-time auction
integration, no bidding automation). Goal: something a buyer can pull up on
their phone at an auction, or an appraiser can glance at during a trade
negotiation, in the time it takes to type a model name.

- Simple form: select Make → Model → (optional) Trim, optional mileage input.
- Returns, instantly, from already-computed data (no new queries beyond what
  the dashboard already runs): recommended max acquisition price band (same
  formula as the Buyer's Target List: median sold retail − target front-gross
  band − flat recon assumption), average days-to-sell for that model,
  preferred acquisition source, current days-supply status (thin/healthy/
  heavy/overstocked), and the low-sample-size flag if applicable.
- Mobile-responsive layout (single column, large touch targets, minimal
  typing) — this is meant to be used standing at an auction lot or a trade
  desk, not at a workstation.
- If this turns out to add meaningful complexity or bug risk beyond a thin
  read-only view over existing aggregates, it's fine to cut for v1 and ship it
  as a fast-follow — do not let it block or destabilize the core dashboard.

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
- [ ] Buyer's Target List is primarily sorted by total gross ÷ days-to-sell,
      with front/back gross shown separately alongside it.
- [ ] Ideal acquisition price subtracts the flat recon-cost setting (default
      $1,600) from median sold retail minus target front gross.
- [ ] Models with fewer than 5 sold units in the selected window are visibly
      flagged as low-sample/directional everywhere they appear.
- [ ] A model that's profitable overall but loses money via one specific
      acquisition source is flagged as "cap bid via [source]," not blanket
      "do not buy."
- [ ] Uploading two overlapping-window snapshots (e.g. 30-day and 90-day in
      the same week) does not silently double-count units in any combined/
      trend view.
- [ ] The Live Acquisition Lookup page returns a result for a model with
      existing data in under a couple of seconds, works on a phone-sized
      screen, and never introduces calculation logic that diverges from the
      main dashboard's numbers.
