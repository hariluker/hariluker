# Golf Hole Flyover SaaS — Phase 0 Architecture Decision Document

**Status:** Draft for product-owner review — no product code has been built yet.
**Date:** 2026-08-08
**Scope:** Product restatement, risk analysis, data/licensing research, architecture and stack recommendation, data model, Brookwood Hole 1 PoC design, Phase 1 acceptance criteria, implementation plan, cost model, open questions.

---

## Executive summary

- **Licensing (the make-or-break question) resolves cleanly.** The US MVP builds entirely on public-domain data: Indiana publishes statewide **15 cm public-domain orthoimagery** (7.5 cm-class in the 2025–28 cycle) and **CC0 lidar** — unusually good for the Fort Wayne pilot; NAIP (30–60 cm) + USGS 3DEP cover the rest of the country. Google, Bing, Mapbox, and Esri are **confirmed unusable** for stored, resold video — Google's terms prohibit it three separate ways. Premium 5.5–15 cm imagery (Hexagon, Vexcel, Nearmap) exists behind negotiated licenses as a later tier. (§3)
- **Rendering: Blender headless on serverless GPU, not a globe engine.** A golf hole is a tiny area — no streaming/tiling needed, which eliminates Cesium's value and its commercial terms. Blender gives the highest determinism, a high visual ceiling (sun/sky, soft shadows, water shaders, and critically **3D tree instancing** to fix the flat-trees problem), byte-reproducible output, and ~**$0.15–0.35 per 1080p render**. A three.js tier provides near-free instant draft previews. (§4)
- **The camera-altitude floor is now a formula, not a hope**: texture stays acceptable down to slant distances of ~2× (imagery cm/px × 1660) — Indiana's 15 cm imagery supports genuine drone-style altitudes, and detail-texture blending extends the floor further. (§4.4)
- **AI is a premium tier, not a dependency.** Deterministic cinematography (supersampling, haze, LUT grade, film grain) delivers an estimated 70–90% of the quality lift for ~$0.01/video with zero geometry risk. Conservative super-resolution adds a 4K tier; diffusion enhancement stays experimental behind an automated geometry-diff QA gate that exploits our own verified feature polygons. (§5)
- **Your two test coordinates fail validation as intended**: they are 242 yd apart against a 520 yd scorecard (47%) — bearing matches the hole, distance doesn't; likely one point marks a mid-fairway landing zone. Phase 1 recalibrates them against licensed imagery. (§8)
- **Unit economics are a non-issue**: standard hole ≈ **$0.20–0.45** all-in compute; the worst-case premium stack stays under ~$5. Regeneration (pin updates, seasonal renders) can be a product feature, not a cost problem. (§13)
- **Plan**: six gated phases; Phases 1–4 run on a laptop + serverless GPU with no cloud commitment; Phase 1 (verified Brookwood Hole 1 geometry, ~2–3 weeks) needs only the scorecard, the reference screenshot, and one calibration confirmation from you. (§12, §14)

---

## 1. Product understanding (restatement)

We are building a web SaaS that lets a non-technical golf course employee generate a **10–12 second cinematic drone-style flyover video** of an individual golf hole, flying from a selected tee to the pin, that looks professionally filmed and **represents the real hole accurately**.

The core mechanic:

1. A course is located; **commercially licensed** aerial imagery and real terrain are acquired for it.
2. The system proposes hole geometry (tee, fairway centerline, green, hazards) via automated detection; a course employee **verifies and corrects it visually** — the human is the geometric authority.
3. A deterministic renderer drapes the licensed imagery over real elevation data and flies a computed camera spline shaped by the hole's actual geometry (not a straight line), producing a reproducible **base render**.
4. An **optional** AI enhancement stage may improve appearance (grass, lighting, sharpness, sky) but is architecturally forbidden from altering geometry, and can be disabled entirely. Both base and enhanced renders are preserved for audit.
5. The course downloads and commercially reuses the video (web, social, apps, scorecards). Therefore **every input asset must carry commercial derivative-work and resale rights** — licensing is a first-class engineering constraint, not an afterthought.

Priorities, in order: **accuracy → commercial viability → user experience → development speed.**

The Brookwood Golf Club (Fort Wayne, IN) Hole 1 pilot exists to prove the foundation, not to be a one-off demo. Every architectural decision below is judged on whether it survives thousands of courses.

### What this product is *not*

- Not a GIS tool — GIS complexity stays behind the curtain.
- Not a generative-AI video product — geography is authored by data + humans, never by a model.
- Not a game-engine visualization — the target aesthetic is restrained broadcast realism.

---

## 2. Highest-risk assumptions

Ranked by (probability of being wrong × cost if wrong):

| # | Assumption at risk | Why it's risky | Mitigation |
|---|---|---|---|
| **R1** | *Commercially safe imagery will look premium at low camera altitude.* | The unambiguously safe US imagery (public-domain government orthophotos) is 15–60 cm/px. A virtual camera at 30–60 m altitude may expose soft textures and "painted-flat" trees. This is the single biggest product risk: if the safe imagery can't sell, we either pay for premium imagery (changes unit economics) or lean harder on enhancement (raises geometry-fidelity risk). *Softened for the pilot by §3.1: Indiana publishes 15 cm public-domain imagery, near the comfortable zone for drone-style altitudes (§4.4) — but the national baseline (NAIP 30–60 cm) remains marginal, so the risk stands for scale-out.* | Phase 3 is a dedicated, gated visual-quality evaluation at multiple altitudes **before** the SaaS build. Camera-altitude floor becomes a computed function of source imagery GSD; detail-texture blending (§4.4) closes the gap. |
| **R2** | *Popular consumer map providers can be used.* They cannot. Google/Apple (and most Bing/Mapbox tiers) prohibit offline rendering, caching, and resale of derived video. Building on them would make the entire product unlicensable. | Provider-abstraction layer; core product built only on sources with verified derivative-work + resale rights (§3). Anything ambiguous is excluded from the render path. |
| **R3** | *Trees will look acceptable.* Orthophotos flatten trees onto the ground plane. On a bare-earth DEM, a camera flying past a tree line sees green-painted pavement. | Use lidar-derived surface data (DSM/canopy height) to give tree areas real volume, and/or instance procedural 3D trees inside detected tree polygons; keep camera geometry (altitude, pitch) inside limits where the effect holds up. Tested explicitly in Phase 3. |
| **R4** | *AI enhancement can improve appearance without moving geometry.* Diffusion-style enhancement at useful strengths is known to hallucinate; temporal flicker is a second failure mode. | Enhancement is optional, off by default, applied only to the base render, and gated by an automated geometry-diff QA (edge/SSIM comparison per frame between base and enhanced) plus human review. Conservative super-resolution before generative approaches. |
| **R5** | *Automated feature detection will be good enough to be helpful.* If detection is bad, the human correction burden makes setup feel like GIS work and kills the UX promise. | Detection ships as *suggestions with confidence scores*; the editor must be pleasant enough that a fully-manual trace of one hole takes < 10 minutes. Detection quality improves post-MVP; it is not on the critical path for Phase 1–2. |
| **R6** | *Imagery is current enough.* Public orthophoto cycles are 2–3 years. A course that renovated a green last season will notice. | Imagery date is stored and shown to the customer during verification ("imagery captured 2024 — confirm it matches your course"); premium-imagery upgrade path (Nearmap/Vexcel/Hexagon) is architected in from day one via the provider abstraction. |
| **R7** | *Third-party golf databases have trustworthy coordinates.* Explicitly assumed false per the brief — and our own Brookwood test data demonstrates it (§8: collected points are 242 yd apart vs a 520 yd scorecard). | Validation engine (§8) compares scorecard yardage vs straight-line vs centerline distance and blocks unverified geometry from rendering. |
| **R8** | *Render cost per video is commercially small.* If a render takes GPU-hours, per-hole pricing breaks. | Cost model in §13; render time is a tracked metric from the first PoC render; frame count is bounded (10–12 s × 30/60 fps). |
| **R9** | *OSM golf polygons can seed our database.* OSM's ODbL share-alike could contaminate our proprietary geometry database. | Treat OSM as UNSAFE for stored seed geometry unless legal review of the "produced work" boundary says otherwise; detection runs on licensed imagery instead. |

---

## 3. Data sources and licensing (the load-bearing decision)

> Licensing verdicts below are engineering-level conclusions from provider terms as researched on 2026-08-08 (source URLs in appendix A). Before commercial launch, counsel should confirm the SAFE column — but the architecture is chosen so that even the strictest reading survives.

### 3.1 The headline finding

**The US MVP can be built entirely on public-domain data — zero licensing risk, zero data cost — and for the Indiana pilot specifically, the public data is unusually good.** Indiana's state imagery program (IGIO/IndianaMap) publishes statewide **6-inch (15 cm) orthophotography as public domain with "no distribution restrictions,"** with the 2025–2028 refresh cycle (Woolpert) specced at 3-inch (7.5 cm) base resolution, and statewide lidar explicitly licensed **CC0** (QL2 today; QL1 at 25 pts/m² incoming — dense enough to model green contours and tree canopy). Both are free via IndianaMap and AWS Open Data. That is premium-adjacent texture and excellent terrain for the pilot at $0.

Conversely, the consumer map platforms everyone assumes are usable are **definitively not**, and the product must never touch them in the render path *or the editor basemap*.

### 3.2 Imagery verdicts

| Source | Verdict | Resolution | Key licensing facts |
|---|---|---|---|
| **Indiana IGIO orthophotos** | **SAFE — pilot texture source** | **15 cm now; 7.5 cm-class 2025–2028 cycle** | Public domain, "no distribution restrictions"; free (IndianaMap, AWS Open Data) |
| **USDA NAIP** | **SAFE — national baseline** | 60 cm baseline; ~half the states at 30 cm per cycle | US federal public domain; free (AWS `naip-visualization` COGs, requester-pays); leaf-on summer capture (green turf — aesthetically helpful) |
| Other state ortho programs | SAFE (verify per state) | varies, often 7.5–15 cm | ~20+ states run public-domain programs; some fly leaf-off — verify per state as we expand |
| **Google Maps Platform** (incl. Photorealistic 3D Tiles, Aerial View API) | **UNSAFE — clearest "no" of the list** | — | No caching > 30 days; no "content based on Google Maps Content"; promo videos capped at 30 s and "may not be resold"; even Google's own Aerial View flyover product forbids customers storing the MP4s. Rendering-and-selling violates three clauses simultaneously |
| Bing / Azure Maps | UNSAFE | 30–50 cm (TomTom/Maxar) | Prohibits server-side tile modification, imagery-product stitching, feature extraction; Bing Enterprise retiring anyway (2028) |
| Mapbox Satellite | UNSAFE without negotiated order | ~30–50 cm (Maxar) | Video-media rights are an enterprise add-on; base terms bar resale of derived print/video; commercial tracing prohibited. Effectively buying a Maxar sublicense at worse-than-NAIP resolution |
| Esri World Imagery | UNSAFE for resale | 30–60 cm (Maxar Vivid + community) | Terms transfer no derivative/redistribution rights; Esri can't sublicense Maxar pixels for our resale regardless |
| USGS HRO archive | Skip | 15 cm–1 m | Program retired 2017; data 10–25 years old; per-county license spot-checks needed |
| OpenAerialMap | SAFE license, unusable coverage | drone-grade | CC-BY 4.0; opportunistic coverage only — but it's the licensing model to copy if we ever fly our own drones |
| **Nearmap / Vexcel / Hexagon / Maxar** (premium tier) | **CONDITIONAL — negotiate, don't self-serve** | 5.5–15 cm aerial; Maxar 15–30 cm satellite | Standard terms are all internal-use-only. Paths that work: **Hexagon HxGN** publicly claims "very liberal licenses for derived products" (full-CONUS 15/30 cm, self-serve store) — get it in license text, not marketing text; **Vexcel** launches nationwide 7.5 cm collection Jan 2027 — needs a partner license; **Nearmap**'s published terms already support an inverted structure where the *course* subscribes and appoints us their visualization/animation contractor; **Maxar** archive is cheap per course (~$25/km², course ≈ 2–3 km²) but needs its media-license tier |

### 3.3 Elevation verdicts

| Source | Verdict | Notes |
|---|---|---|
| **Indiana GIO lidar** | **SAFE — pilot terrain source** | Explicitly CC0; QL2 statewide (±1 ft vertical), QL1 25 pts/m² in the 2025–2028 program; free (AWS Open Data). Derive our own DTM + canopy-height model from the point cloud rather than using the 1 m DEM — greens undulations and tree heights both come from this |
| **USGS 3DEP** | **SAFE — national baseline** | Public domain; 1 m DEM + lidar point clouds nationwide; Allen County inside Indiana's statewide QL2 block |
| Cesium World Terrain | CONDITIONAL, unnecessary | Video renders permitted with attribution + paid plan, but it's coarser than free 3DEP — no reason to pay |
| SRTM / Copernicus GLO-30 | SAFE, background only | ~30 m — a green is one pixel; only for distant horizon hills |

### 3.4 OpenStreetMap (refining risk R9)

Research sharpened this: our rendered videos are ODbL **"Produced Works"** — publishing them does *not* force our database open even if OSM-seeded geometry sits inside it (OSMF Licence & Legal FAQ). The real obligations are (1) attribution on the produced work, and (2) if we ever *publicly expose the derivative database itself* (an API serving polygons, an interactive overlay-as-data), it must be offered under ODbL on request; nationwide golf-polygon extraction is a "Substantial" extract. Policy: OSM-seeded geometry, if used at all, lives in a segregated layer with attribution; but since every hole gets a human verification pass against our own PD imagery anyway, **hand-digitized geometry traced from public-domain imagery is 100% ours with zero obligations — and is the default**. This is cheaper than ODbL compliance bookkeeping.

### 3.5 Licensing architecture consequences

1. Every `CourseAsset` references a `License` row (§9) — commercial/derivative/resale flags are queryable, per the brief's "licensing is first-class" requirement.
2. The **editor basemap is our own licensed imagery** served from our COG store — no consumer tiles anywhere in the product, ever.
3. The premium-imagery question (Nearmap-inversion vs Hexagon vs Vexcel-2027 vs own-drone photogrammetry — which at sub-5 cm and full ownership may beat all of them per course) is deliberately deferred to the Phase 3 gate, where side-by-side renders let us decide with evidence.
4. Open follow-ups before any commercial contract: HxGN EULA text on third-party distribution; Nearmap/Vexcel/Maxar actual pricing (all quote-based); IGIO 3-inch-vs-6-inch spec discrepancy for the 2025–2028 cycle and Allen County's flight year.

---

## 4. Rendering architecture

### 4.1 The reframing that decides it

A golf hole is a tiny area of interest (~500 m × 1.5 km). At 1 m DEM resolution that is ~1–2 M terrain vertices, and the entire orthophoto fits in a single 4K–8K texture. **We do not need streaming, tiling, LOD, or a globe engine.** That eliminates the apparent front-runner (CesiumJS/Cesium ion): its core value is globally streamed terrain we don't need, it adds tile-pipeline and browser-automation complexity, and Cesium ion's streamed assets carry commercial terms ($149–874/mo) we'd otherwise have to engineer around. The real question is *which offline renderer gives the best look per dollar with full determinism*.

### 4.2 Options compared

| Approach | Determinism | Visual ceiling | Cost / 1080p30 video | Ops burden | Licensing | Verdict |
|---|---|---|---|---|---|---|
| **Blender headless (bpy), Eevee Next / Cycles** | **High** (fixed seeds, scripted scene, pinned container) | **High** — sun/sky model, soft shadows, DOF, motion blur, water shaders, geometry-node tree instancing | ~$0.20–0.35 Eevee; $1–2.50 Cycles | Low-med: one Python script, one Docker image, headless GPU works (EGL/OptiX) | GPL engine, but scripts & rendered output unencumbered; no per-render fees | **Primary** |
| three.js custom heightfield in headless Chromium | Med-high (pin Chromium+driver; stepped clock) | Medium | < $0.05, 1–3 min | Medium (own the terrain/camera code) | MIT | **Draft-preview tier + fallback** |
| CesiumJS + headless Chromium | Medium (load-state races) | Medium (no soft shadows/GI) | ~$0.02–0.05 | Med-high | CesiumJS Apache-2.0; ion commercial | Skip — no benefit at this AOI size |
| Unreal + Cesium for Unreal (Movie Render Queue) | Medium (temporal systems to tame) | Highest (Lumen/Nanite foliage) | $0.50–1.50 + heavy images (30–80 GB) | **High** | Free < $1M revenue, then $1,850/seat/yr | Revisit only if quality becomes the differentiator |
| Godot headless | High (`--write-movie`) | Medium | $0.05–0.15 | Medium, no geo ecosystem | MIT | No edge over Blender/three.js |
| Gaussian splatting / NeRF | Low-med | Photoreal *if* multi-view oblique input exists — nadir ortho gives splats nothing a mesh lacks | training $1–5/scene | Research-grade | Mixed | Not ready; revisit in 12–24 mo or with oblique imagery |

### 4.3 Chosen pipeline (per render)

1. GDAL warps DEM + ortho to the course's UTM CRS, clips to hole AOI + buffer.
2. A bpy (Blender Python) script — a pure function of *(input rasters, geometry JSON, camera JSON, style params, seed)* — builds a displaced grid mesh from the DEM, drapes the ortho, adds a Nishita sun/sky (sun azimuth/elevation are deterministic style inputs: "morning look" vs "late-afternoon look" become product features), scatters seeded low-poly tree instances on the canopy mask, places a 3D flagstick at the pin, animates the camera along the computed spline.
3. Frames render to PNG (Eevee Next standard tier; Cycles behind a premium flag), then ffmpeg assembles with bit-exact settings: `libx264 -preset slow -crf 18 -pix_fmt yuv420p -x264-params threads=4 -fflags +bitexact -flags +bitexact -map_metadata -1 -movflags +faststart` (libx265 for 4K). CPU encode, never NVENC — NVENC has no cross-driver bit guarantees.
4. Overlays (logo, hole number, par, yardage) composite deterministically as vector layers in the encode step, never inside any AI stage.

**Determinism contract:** identical inputs on a pinned container (Blender version + NVIDIA driver + one GPU family, e.g. all-L4) produce identical frames; encoder settings above make the MP4 byte-reproducible. Cross-GPU-generation bit-identity is not guaranteed (float ordering), so a GPU-family migration is treated as an engine version bump — which the `Render` record already tracks.

### 4.4 How low can the camera fly? (the §"Image Quality Problem" answer)

For a 1080p frame at ~60° horizontal FOV, ground footprint per screen pixel ≈ slant-distance / 1660. Texture is 1:1 sharp when slant distance ≥ 1660 × texel size; ~2× magnification stays acceptable in motion; ~4× reads as smeared.

| Source imagery | Sharp at slant ≥ | Acceptable to (~2×) | Fails below (~4×) |
|---|---|---|---|
| 60 cm/px (NAIP baseline) | ~1000 m | ~500 m | ~250 m |
| 30 cm/px (NAIP better states) | ~500 m | ~250 m | ~125 m |
| **15 cm/px (Indiana today)** | ~250 m | ~125 m | ~60 m |
| 7.5 cm/px (premium / Indiana 2025–28 cycle) | ~125 m | ~60 m | ~30 m |

A convincing drone flyover wants 40–100 m AGL with 20–40° downward pitch → slant distances of 100–350 m. Conclusions: **7.5 cm imagery is comfortable; 30 cm is marginal; 60 cm alone cannot support low flight.** Mitigations, in priority order:

1. **Detail-texture blending** (the decisive one): tile a 1–2 cm/px grass/sand micro-texture hue-modulated by the ortho color, masked by our own fairway/green/bunker vectors so each surface gets the right micro-texture. This is the standard game-engine technique and carries close-ups down to ~10–20 m AGL while the ortho provides macro color. Fully deterministic.
2. **Camera floor as a function of imagery GSD**: the spline solver enforces a minimum slant distance derived from the source imagery's cm/px — camera quality physically cannot outrun the data.
3. Optional conservative 2–4× super-resolution of the ortho as preprocessing (turf-safe; kept off buildings/paths — see §5).

### 4.5 The flat-trees problem

Draping ortho on bare-earth DEM paints trees onto the ground — instantly fake at oblique angles. Chosen fix: **DEM ground + procedural 3D tree instancing.** Compute a canopy height model (lidar first-return DSM − DEM, threshold > 2–3 m); scatter seeded, deterministic low-poly tree instances with heights from the CHM inside tree polygons; their cast shadows sell the 3D. This is ~50 lines of Blender geometry nodes and is the single biggest visual upgrade available — and a strong reason Blender beats browser renderers. Fallback orderings (DSM "melted-ice-cream" lumps, or camera discipline keeping pitch ≥ 30° down) remain available, and the spline solver never lets the camera look horizon-ward across painted trees regardless.

### 4.6 Other known visual risks

- **Double shadows** (ortho has baked shadows + renderer sun): prefer low-shadow imagery, keep the virtual sun near the imagery's sun azimuth, bias toward ambient-dominant lighting.
- **DEM/ortho misregistration** (different vintages): subpixel co-registration check per course at acquisition time; render QA looks for bunker "slide" on slopes.
- **Painted water**: replace water polygons with a seeded animated water shader — cheap, deterministic, large perceived-quality win.
- **World edge**: low-res terrain skirt + atmospheric haze + matched sky gradient so the AOI boundary is never visible.

### 4.7 Compute platform

Serverless GPU (Modal-style, per-second billing; L4 ≈ $0.80/hr, T4 ≈ $0.59/hr) for render workers: bursty per-render jobs, exact GPU-seconds per render for the cost ledger, and determinism makes spot/retry safe. A week-one task is benchmarking a representative hole scene on T4 vs L4 — the per-frame times in §13 are scaling estimates, not measurements of our exact scene.

---

## 5. AI enhancement & automatic feature detection

### 5.1 Enhancement: the counterintuitive finding

**Deterministic, non-AI cinematography is ~70–90% of the achievable quality lift, at roughly $0.01/video.** A supersampled render with depth-based atmospheric haze, soft shadows/ambient occlusion, a matched sky, then a film-emulation LUT grade, smart sharpening, and fine film grain reads dramatically more "cinematic" than a raw render pushed through the fanciest upscaler — and it is temporally perfect, license-free, and geometry-exact by construction. Film grain in particular masks source-texture softness remarkably well. This is the default "Championship Broadcast" style, and it means **AI enhancement is a premium tier, not a dependency** — exactly the posture the quality philosophy demands.

### 5.2 Enhancement tiers

| Tier | What | Geometry risk | Temporal risk | License | Cost / 10 s video |
|---|---|---|---|---|---|
| **A — Deterministic grade** (default, ships first) | Supersampling, haze, sky, shadows in-renderer; LUT + sharpen + grain in post | None | None | N/A | ~$0.00–0.01 |
| **B — Conservative super-resolution** (4K tier) | Render 1080p → 2× SR → 4K. BasicVSR++ (Apache-2.0, recurrent → best flicker resistance) or Real-ESRGAN (BSD-3) with temporal blending, self-hosted on serverless GPU; or the official **Topaz API** (~$0.80/10 s 4K, fidelity-oriented, zero infra) | Low — micro-texture synthesis only, structures unmoved | Low (video-native models) | All clear | $0.05–0.20 self-host; ~$0.80 Topaz API |
| **C — Diffusion "premium look"** (experimental, Phase 4, off by default) | SDXL + ControlNet-Tile at denoise ≤ 0.20, or a video-native enhancer, followed by the QA gate below | Real above ~0.25 denoise — small high-contrast features (i.e., **bunkers**) are the first casualties | Real — flicker is the weakest link even at low denoise | SDXL OpenRAIL++-M OK; avoid SD3.x (< $1M revenue cap) | $1–4 |

Ruled out: **VRT/RVRT** (CC-BY-NC, non-commercial), **Topaz desktop app** (EULA excludes server/automated use; $1M revenue cap on standard tiers — the official Topaz *API* is the sanctioned path), and **generative video models (Runway/Kling/Veo/Sora-class) for per-course deliverables** — their commercial terms are actually fine on paid tiers, but they re-synthesize every frame and will reshape bunkers and invent/delete trees with no knob low enough to prevent it. Fidelity, not licensing, disqualifies them.

Two cheaper substitutes always considered before SR: supersampling (render high, downsample — "SR" with zero hallucination) and *buying better imagery* where available, which beats any model.

### 5.3 The geometry QA gate (applies to any tier above A)

Because verified feature polygons exist in our own database, enhancement QA is mechanical, not subjective:

1. Per frame: edge-map (Canny/HED) + SSIM comparison between base and enhanced frames.
2. Per feature: project each verified bunker/green/water polygon into screen space and compare region IoU between base and enhanced — auto-**reject the clip** if any feature region shifts beyond threshold.
3. Rejections surface in the QA interface with side-by-side playback and a difference overlay; humans spot-check.
4. Both renders are always retained (§7), so any customer dispute is answerable by diffing.

### 5.4 Feature detection strategy (human-in-the-loop MVP)

| Component | Role | License |
|---|---|---|
| **SAM2 interactive assist** (the highest-leverage piece) | Server-side image encoder embeds the ortho tile once; the small mask decoder runs in-browser (ONNX) → employee clicks a bunker, gets an instant editable mask, assigns the class. Strong on high-contrast features (bunkers, water, greens); weak on fuzzy fairway/rough edges — human draws those | Apache-2.0 ✓ |
| Classical CV first pass | HSV threshold + morphology finds bunker (bright sand) and water (dark/smooth) candidates that pre-stage SAM prompts, so the editor opens with suggestions already placed | ours |
| Vision LLM classification | Auto-labels accepted masks ("bunker, not sand-colored cart path") and sanity-checks counts; never draws geometry — not polygon-precise | API terms |
| OSM golf polygons | **Not stored in our database** (ODbL share-alike contamination risk, §2 R9). At most: transient visual hinting during setup, pending counsel review. US coverage is uneven anyway | ODbL ⚠️ |
| Fine-tuned segmentation (later) | Every human correction is logged, quietly building a proprietary, correctly-licensed US golf training set; fine-tune SegFormer/Mask2Former on it post-MVP to move from "click-assisted" to "review-only." (The Danish Golf Courses dataset — 1,123 orthophotos, 107 courses, ~70% mIoU baselines — proves feasibility but is ODbL and Danish-domain; useful for experiments, not for shipped weights without counsel review) | build our own |

Every suggestion enters the editor as a `Feature` with `provenance='detected'`, a confidence score, and `verification='unreviewed'` — detection is never silently truth, per the brief. Realistic segmentation ceiling is ~75–85% IoU, which is a *suggestion* quality level; the architecture assumes a human pass forever, and gets faster over time rather than promising full automation.

---

## 6. Recommended architecture & stack

### 6.1 System shape

```
                        ┌────────────────────────────────────────────┐
                        │                Web app (SaaS)              │
                        │  course search · geometry editor · render  │
                        │  config · preview · download · QA console  │
                        └───────────────┬────────────────────────────┘
                                        │ HTTPS/JSON
                        ┌───────────────▼───────────────┐
                        │        API + domain core      │
                        │  courses · holes · geometry   │
                        │  validation engine · renders  │
                        │  auth · orgs · audit          │
                        └──┬──────────┬──────────┬──────┘
                           │          │          │ job queue
        ┌──────────────────▼──┐  ┌────▼─────┐  ┌─▼──────────────────────────┐
        │  Geo acquisition    │  │ Postgres │  │  Render workers (GPU)      │
        │  worker (CPU)       │  │ +PostGIS │  │  camera solver → Blender   │
        │  imagery/DEM fetch, │  └──────────┘  │  bpy → ffmpeg → QA diff    │
        │  reproject, COG,    │  ┌──────────┐  │  (enhancement workers      │
        │  co-registration,   │  │  Object  │  │   separate, optional)      │
        │  detection prestage │  │  storage │  └────────────────────────────┘
        └─────────────────────┘  └──────────┘
```

Provider abstraction sits at four seams, each a small interface with swappable implementations and a `License` row attached to everything that crosses it: **ImageryProvider**, **TerrainProvider**, **EnhancementProvider**, **RenderBackend**.

### 6.2 Stack choices and why

| Layer | Choice | Why (and what was rejected) |
|---|---|---|
| Language split | **TypeScript** (web app + API) / **Python** (geospatial + render workers) | The geospatial and rendering ecosystems (GDAL, rasterio, shapely, pyproj, bpy, PyTorch) are Python-native; fighting that from Node is self-harm. The web ecosystem is TS-native. Two languages is a real cost, accepted deliberately; the contract between them is the database + queue + typed JSON schemas, not shared code. |
| Web app | **Next.js + React** | Boring, hireable, excellent map-editor ecosystem. |
| Map editor | **MapLibre GL JS** (BSD) + Terra Draw for editing, rendering *our* COG imagery tiles via TiTiler | MapLibre is the license-safe fork of Mapbox GL (Mapbox GL v2+ requires Mapbox billing). Critically, the editor basemap is our own licensed imagery — no consumer tiles anywhere, per §11 crit. 1. |
| API | **FastAPI** (Python) | Keeps validation rules, geodesy, and camera-solver in one language with one test suite; auto-generated OpenAPI gives the TS frontend typed clients. (Considered NestJS + separate Python service; rejected — the domain core *is* geospatial, so the API belongs where the geo code lives.) |
| Database | **PostgreSQL + PostGIS** | The industry-standard spatial database; validation rules become spatial SQL + application code; migrations via Alembic. JSON-blob geometry storage was rejected (§9). |
| Object storage | **S3-compatible** (imagery COGs, DEM tiles, frames, videos, QA packets) | Signed URLs for customer downloads; lifecycle rules for frame cleanup. |
| Queue / jobs | Postgres-backed queue (e.g. Procrastinate/pg-boss-style) for MVP; SQS-class later | One less system to run; render volume is bursty-low for a long time. |
| Geo processing | **GDAL/rasterio/shapely/pyproj + GeographicLib** | The only serious choice. |
| Render | **Blender headless (bpy) on serverless GPU (L4)**; three.js draft tier | §4. |
| Enhancement | Tier A in-pipeline; Tier B on serverless GPU or Topaz API | §5. |
| Auth | Managed auth (Auth0/Clerk/WorkOS-class) with org + role model from day one | Building auth is undifferentiated risk; org/role schema (§9) is ours either way. |
| Hosting | Container-first (Docker) so PoC runs on a laptop; cloud target decided with product owner (§14 Q4). Render workers on Modal-class serverless GPU regardless of where the API lives | Phase 1 has no cloud dependency at all. |
| Observability | Structured logs + per-stage timing/cost written to the `Render` record itself | The cost ledger is a product requirement (§13), not an ops nicety. |

### 6.3 Alternatives considered at the architecture level

- **Cesium-centric web renderer end-to-end** (edit and render in one engine): rejected — §4.1; browser-render determinism is weaker, visual ceiling lower, and ion licensing adds a commercial dependency for zero benefit at hole scale.
- **Game engine end-to-end (Unreal)**: highest visual ceiling, but 30–80 GB images, headless quirks, seat licensing at scale, and determinism work; revisit only if Phase 3 says Blender's ceiling can't sell.
- **Generative-video-first product** (render rough, let AI make it pretty): rejected on the core quality philosophy — geometry authority cannot be delegated to a model, and §5.2 shows current models can't hold geometry anyway.
- **Buying golf GPS vendor data as geometry source**: rejected as a *foundation* (brief explicitly distrusts it; our own test data proves the point) but the architecture's import path (`created_from='import'` + mandatory human verification + validation) leaves the door open as a *prefill* if a licensable feed appears.
- **Single-language (all-TS or all-Python)**: rejected; see stack table.

---

## 7. Deterministic vs. AI-generated boundary

A single principle decides every case: **anything that defines *where things are* or *what the course is* must be deterministic; AI may only touch *how pixels look*, and only in a stage that can be diffed against the deterministic result and switched off.**

| Subsystem | Deterministic | AI-assisted | AI-generated |
|---|---|---|---|
| Course/hole geometry (tees, fairway, green, hazards) | ✅ source of truth (imagery + human verification) | Detection *suggestions only*, confidence-scored, human-approved | ❌ never |
| Terrain surface | ✅ real DEM/DSM | — | ❌ never |
| Camera path | ✅ computed from verified geometry + terrain | — | ❌ never |
| Base render | ✅ reproducible byte-stable frames | — | ❌ |
| Text, logos, yardages, overlays | ✅ vector/deterministic compositing | — | ❌ never (AI text is illegible/wrong) |
| Sky | ✅ deterministic sky dome/HDRI in renderer | — | ❌ generative sky replacement deferred |
| Color/lighting/grain | ✅ LUT-based grade | — | — |
| Detail enhancement | — | Conservative super-resolution with geometry-diff QA | Diffusion enhancement only as an experimental, gated, per-frame-QA'd option (Phase 4) |
| Validation verdicts | ✅ rule-based, explainable | — | ❌ |

Both the base render and any enhanced render are persisted, and the QA interface can play them side-by-side with a difference overlay — that is how we answer "your video moved my bunker" (§11).

---

## 8. Geometry validation design (with the Brookwood worked example)

### 8.1 The Brookwood coordinate conflict, quantified

The two coordinates collected during testing:

- Point A: `40.991165803512786, -85.17242986112421`
- Point B: `40.99273417763863, -85.17405958051316`

Geodesic distance: **221.6 m = 242.4 yd**, bearing A→B = **322° (northwest)**.

The bearing is *consistent* with the screenshot (tee lower-right, green upper-left), but the distance is **47% of the 520-yd scorecard yardage**. A dogleg makes straight-line distance *shorter* than routed yardage, but rarely below ~80% for a playable routing — 47% is far outside that. Most probable explanations, in order: (1) one point marks a mid-fairway landing zone or layup target rather than the green center — 242 yd is a plausible drive distance, and golf-app route lines often have draggable midpoints; (2) a misclick at low zoom; (3) points captured from two different holes. **Verdict: FAIL — neither point may be persisted as tee or green until re-captured against calibrated imagery in the Phase 1 editor.** This is exactly the failure class the validation engine exists to catch.

### 8.2 Validation rules (Phase 1 scope)

Each verified `HoleGeometry` runs a rule pipeline; every rule emits `PASS | REVIEW | FAIL`, a human-readable explanation, and the numbers behind it. The hole's overall status is the worst individual result. `FAIL` blocks rendering; `REVIEW` allows rendering but flags the hole in QA and in the editor UI.

| Rule | Logic | Thresholds (initial, tunable) |
|---|---|---|
| **Straight-line vs scorecard** | geodesic(tee, green-center) / scorecard yardage | ≥ 0.80 PASS · 0.60–0.80 REVIEW (doglegs) · < 0.60 or > 1.10 FAIL |
| **Centerline vs scorecard** | length of fairway centerline (tee→green) / scorecard yardage | 0.93–1.07 PASS · 0.85–1.15 REVIEW · else FAIL — centerline should approximate routed yardage closely |
| **Centerline endpoints** | first vertex within N m of tee, last within green polygon (or M m of center) | 20 m / inside-polygon PASS; else REVIEW |
| **Par vs yardage plausibility** | yardage within conventional par band (par 3: 60–260 yd, par 4: 240–520, par 5: 400–700) | outside band → REVIEW |
| **Green sanity** | green polygon area 150–2,500 m², roughly convex, contains pin | outside → REVIEW; pin outside green polygon → FAIL |
| **Tee/green elevation sanity** | tee & green elevations sampled from DEM within ±3 m of any user-entered elevation; tee-green Δ < 60 m | else REVIEW |
| **Containment** | tee, centerline, green all inside course boundary (when known) | outside → REVIEW |
| **Self-intersection / degeneracy** | polygons valid (no self-intersection), centerline non-self-crossing, ≥ 3 vertices | invalid → FAIL |
| **Imagery/terrain coverage** | full hole envelope (+80 m buffer) covered by acquired imagery & DEM tiles | gaps → FAIL |

The editor surfaces failures in plain English: *"Your tee and green are 242 yards apart in a straight line, but Hole 1 is listed at 520 yards. Doglegs shorten the straight-line distance, but not this much — one of these points is probably misplaced. Drag the marker to the correct spot."*

### 8.3 Geodesy conventions

- Coordinates stored as WGS84 (EPSG:4326); all distance/bearing math geodesic (GeographicLib/Karney via standard libraries), never naive lat/lon Euclidean.
- Local computation (camera splines, offsets, areas) in an automatically selected UTM zone (EPSG:326xx; Brookwood → UTM 16N, EPSG:32616), converting once at the boundary.
- Elevations in meters above the ellipsoid internally, with geoid offset stored per course; yardages displayed in yards, computed in meters.
- These conversions are the first code to get unit tests (against published geodesic test vectors).

---

## 9. Data model (initial)

Improvements over the conceptual schema in the brief: (a) **course-level shared assets** (imagery, terrain, detection runs, branding) are first-class entities that holes reference, so hole 2 costs no re-acquisition; (b) every geometry feature carries a uniform `provenance` + `confidence` + `verification` envelope instead of per-type ad-hoc fields; (c) **renders are immutable jobs** referencing an immutable geometry *version*, giving reproducibility and audit for free; (d) pins are a separate lightweight entity so daily pin updates never touch verified geometry.

PostgreSQL + PostGIS; geometry columns are real PostGIS types (`geography(Point)`, `geometry(Polygon, 4326)`, `geometry(LineString, 4326)`), not JSON blobs — validation rules run in the database's spatial engine as well as in application code.

```
Organization            — id, name, plan, billing_ref (later)
  User                  — id, org_id, email, role (owner|editor|viewer)

Course                  — id, org_id, name, address, centroid (Point),
                          boundary (Polygon, nullable), hole_count, timezone,
                          status (draft|active|archived)
  CourseAsset           — id, course_id, kind (orthoimagery|dem|dsm|canopy|detection_raster),
                          provider, provider_ref, license_id, capture_date,
                          resolution_m_per_px, crs, footprint (Polygon),
                          storage_uri, checksum, acquired_at
  License               — id, provider, license_name, commercial_use, derivative_ok,
                          resale_ok, attribution_text, terms_url, verified_on
                          # every asset points at the license it was acquired under —
                          # licensing is queryable, not tribal knowledge
  Branding              — id, course_id, logo_uri, colors[], typography,
                          intro_style, outro_style, sponsor fields

Hole                    — id, course_id, number, par, scorecard_yardages jsonb (per tee)
  HoleGeometryVersion   — id, hole_id, version, status (draft|verified|superseded),
                          verified_by, verified_at,
                          validation_result jsonb (per-rule verdicts + numbers),
                          created_from (detection_run_id | manual | import)
    Feature             — id, geometry_version_id,
                          type (tee|fairway_centerline|fairway|green|bunker|water|
                                cart_path|tree_area|building|other_hazard),
                          name (e.g. "Back"), geom (Point|LineString|Polygon),
                          elevation_m (nullable),
                          provenance (detected|user_drawn|user_adjusted|imported),
                          confidence (0–1, null for user-drawn),
                          verification (unreviewed|confirmed|corrected|rejected)
  PinPlacement          — id, hole_id, mode (green_center|custom), point (Point),
                          effective_date, created_by
                          # regenerating for a new pin = new PinPlacement + new Render,
                          # geometry version untouched

DetectionRun            — id, course_id, asset_ids[], model, model_version, params,
                          started/finished, cost, raw_output_uri
                          # suggestions land as Features with provenance='detected'

CameraPath              — id, geometry_version_id, pin_placement_id, algorithm_version,
                          params jsonb, duration_s,
                          keyframes jsonb [{t, lat, lon, ele_agl, look_at, pitch, yaw,
                                            roll, speed}],
                          computed_checksum
                          # derived + cached; recomputable from inputs, stored for audit

Render                  — id, hole_id, geometry_version_id, camera_path_id,
                          pin_placement_id, profile (resolution, fps, aspect, style,
                          overlays, branding_snapshot) jsonb,
                          engine_version, seed/config_checksum,
                          status (queued|rendering|enhancing|qa|done|failed),
                          base_output_uri, enhanced_output_uri (nullable),
                          enhancement (none|sr|experimental) + model + version,
                          qa jsonb (geometry-diff scores, reviewer, verdict),
                          timings jsonb (per-stage), costs jsonb (per-stage),
                          error, created_by, created_at

AuditLog                — id, org_id, actor, action, entity, before/after, at
```

Notes:

- **Reproducibility:** `Render` pins geometry version + camera path checksum + engine version + profile; resubmitting the identical tuple must yield byte-identical base frames (encoder settings fixed). Enhanced output is allowed variance and is stored separately.
- **18-hole reuse:** `CourseAsset` acquisition happens once per course; holes share it. Branding is a snapshot inside the render profile so old renders don't mutate when branding changes.
- **Traceability chain for QA:** customer complaint → Render → geometry version → per-feature provenance (detected vs user-corrected) → detection run → source asset → license. Every link is a foreign key.

---

## 10. Brookwood Hole 1 proof-of-concept workflow (Phase 1)

Goal: a **verified, validated `HoleGeometryVersion` for Brookwood Hole 1** built entirely from commercially safe data — no video yet.

1. **Acquire course assets.** Pull orthoimagery and lidar-derived DEM/DSM tiles for a bounding box around Brookwood (course centroid ≈ 40.99, -85.17, Fort Wayne / Allen County, IN) from the selected public sources (§3). Record provider, capture date, resolution, license row, checksums → `CourseAsset` rows. Reproject to UTM 16N working CRS; build COG (cloud-optimized GeoTIFF) pyramids for the editor.
2. **Stand up the minimal geometry editor.** Web map showing *our* licensed imagery (not a consumer map), with tools: place tee marker; draw/edit fairway centerline (add/move/delete vertices); draw/adjust green polygon; place pin (default = polygon centroid); draw bunker/water polygons. Every edit writes `Feature` rows with provenance.
3. **Trace Hole 1 manually.** Using the reference screenshot *only as visual orientation* (its pixels never enter the system), identify the hole-1 corridor on our licensed imagery and trace tee (back), centerline, green, and the obvious bunkers/water.
4. **Calibrate the disputed coordinates.** Plot points A and B from §8.1 on the licensed imagery; determine what each actually marks; re-capture true back-tee and green-center coordinates from the imagery. Expect the validation engine to FAIL the original pair and PASS the corrected geometry.
5. **Sample terrain.** Attach DEM elevations to tee, green, and centerline vertices; compute the elevation profile along the centerline (this later drives the camera).
6. **Run validation.** Full §8.2 rule pipeline; iterate on tracing until PASS (or documented REVIEW with justification).
7. **Verify and freeze.** Mark geometry version `verified`; record who/when; export a QA packet (imagery + geometry overlay rendering, validation report, elevation profile) for the Phase 1 gate review.

Deliverables: running acquisition pipeline, editor good enough for one hole, verified Hole 1 geometry, validation report, and the calibration write-up resolving points A/B.

---

## 11. Phase 1 acceptance criteria (PASS gate)

Phase 1 passes only if **all** of the following hold:

1. **Licensing:** every byte of imagery/terrain in the system has a `License` row with `commercial_use`, `derivative_ok`, and `resale_ok` all true, with terms URL and verification date. No consumer-map tiles anywhere, including the editor basemap.
2. **Coverage & quality:** acquired imagery fully covers Hole 1 + 80 m buffer at ≤ 60 cm/px with a recorded capture date; DEM at ≤ 1 m resolution covers the same envelope.
3. **Geometry completeness:** verified back tee (point), fairway centerline (≥ 5 vertices honoring the actual routing), green polygon, pin, and at least the major bunkers/water traced with correct provenance metadata.
4. **Validation:** the original A/B coordinate pair is FAILed by the engine with a human-readable explanation; the corrected geometry PASSes; centerline length is within 7% of the 520-yd scorecard yardage (or the discrepancy is explained and signed off — e.g., scorecard measures to green center via dogleg points).
5. **Terrain:** tee/green/centerline elevations sampled from the DEM; elevation profile along the centerline produced and visually sane (no spikes/voids).
6. **Reproducibility:** re-running acquisition + validation from a clean checkout with documented setup yields the same asset checksums and the same validation verdicts.
7. **Tests:** unit tests green for geodesic distance, bearing, CRS conversion, centerline length, polygon validity, and each validation rule (including a fixture reproducing the A/B failure).
8. **Human gate:** product owner reviews the QA packet and confirms the reconstructed hole matches reality (they know the course; we don't).

Explicit non-goals for Phase 1: camera, video, AI, auth, billing, multi-course UI.

---

## 12. Implementation plan

Phases match the brief; each ends at its quality gate with a written QA packet, and nothing advances on "technically works" alone.

### Phase 0 — Research & architecture *(this document — done pending your review)*

### Phase 1 — Brookwood Hole 1 geographic PoC (~2–3 weeks of work)

| Step | Work | Exit artifact |
|---|---|---|
| 1.1 | Repo scaffolding: monorepo (`apps/web`, `services/api`, `services/geo`, `packages/shared-types`), Docker Compose (Postgres+PostGIS, MinIO), CI running tests + linting | Reproducible dev env, documented setup |
| 1.2 | Geodesy core + tests first: geodesic distance/bearing, CRS conversion (WGS84↔UTM), centerline length, polygon validity — tested against published geodesic vectors | Green test suite for all §8.3 math |
| 1.3 | Data model migration v1 (§9 subset: Course, CourseAsset, License, Hole, HoleGeometryVersion, Feature, PinPlacement) | Migrations + seed for Brookwood |
| 1.4 | Acquisition pipeline: fetch Indiana IGIO ortho + GIO lidar tiles for the Brookwood bounding box from AWS Open Data; derive DTM + canopy-height model from the point cloud; reproject to UTM 16N; build COGs; co-registration check; license + checksum records | `CourseAsset` rows + rasters in object storage |
| 1.5 | Minimal editor: MapLibre + TiTiler serving our COGs; tee marker, centerline vertex editing, green/hazard polygons, pin placement; features persist with provenance | Editor usable for one hole |
| 1.6 | Validation engine: all §8.2 rules with explanations; fixture reproducing the A/B coordinate failure | Validation report UI + tests |
| 1.7 | Trace & calibrate Hole 1 (§10 steps 3–7), including resolving points A/B against the imagery | Verified geometry + QA packet |
| **Gate** | §11 criteria reviewed with you | PASS → Phase 2 |

### Phase 2 — Deterministic camera + base render (~2–3 weeks)

Camera-path solver (centerline-following spline with terrain clearance, slant-distance floor from imagery GSD, dogleg banking, green-orbit finish, easing profile per the brief's creative timing guide; par-based duration); Blender bpy scene builder (terrain mesh, ortho drape, sun/sky, tree instancing from CHM, flagstick, water shader); frame render + bit-exact ffmpeg encode; three.js draft preview; render worker on serverless GPU with per-stage timing/cost ledger; reproducibility test (two runs → identical checksums). **Gate:** smooth professional flight over the real hole, byte-reproducible.

### Phase 3 — Visual quality evaluation (~1 week)

Render Brookwood Hole 1 at multiple altitude floors, with/without detail-texture blending and tree instancing; 15 cm vs degraded-to-60 cm source comparison (proxy for NAIP-only states); document with stills + clips. **Gate: "would a golf course pay for this?"** — your call, with evidence. This gate also decides whether the premium-imagery conversation starts now or later.

### Phase 4 — Optional AI enhancement (~1–2 weeks)

Tier A grading ships inside Phase 2 (it's deterministic). Phase 4 proper: 2× SR tier (BasicVSR++/Real-ESRGAN self-host vs Topaz API bake-off), geometry QA gate (edge/SSIM + feature-region IoU), side-by-side QA UI. **Gate:** enhancement visibly improves without geometry drift, and can be disabled.

### Phase 5 — Basic SaaS workflow (~3–4 weeks)

Auth + orgs/roles, course search & creation flow, the simple "Create Hole Flyover" screen from the brief, render queue + status + preview + signed download, SAM2-assisted editor upgrade, branding storage + overlay compositing, QA console v1 (§ Admin/QA), audit logging. **Gate:** a nontechnical employee generates a flyover unassisted.

### Phase 6 — Course-wide workflow

All-18 generation reusing course assets, aspect-ratio variants (9:16, 1:1 via camera reframe — not crop), pin-update regeneration flow, cost dashboards.

Sequencing note: Phases 1–4 are deliberately runnable by one engineer on a laptop + serverless GPU account, with no cloud commitment until Phase 5.

---

## 13. Cost model (per generated hole)

All render/enhancement figures are scaling estimates pending the week-one Phase 2 benchmark (flagged in §4.7); data costs are exact.

### 13.1 Variable cost per generated hole (standard product: 1080p30, Tier A grading)

| Stage | Cost | Notes |
|---|---|---|
| Imagery + terrain data | **$0.00** | Public domain (Indiana/NAIP/3DEP); pennies of egress from AWS Open Data, amortized per course |
| Geo prep (CPU: warp, clip, mesh inputs) | ~$0.01–0.03 | Minutes of CPU |
| Base render, Eevee 1080p30, ~330 frames on L4 (~$0.80/hr serverless, per-second billing) | **~$0.15–0.35** | 12–25 min wall time; spot-safe because deterministic |
| Tier A grade + bit-exact encode | ~$0.00–0.01 | CPU |
| Storage (video + geometry; frames deleted post-QA) | ~$0.01/mo | Object storage |
| Bandwidth (downloads) | ~$0.01–0.05 | Per download |
| **Total, standard hole** | **≈ $0.20–0.45** | |

### 13.2 Premium options (additive)

| Option | Added cost |
|---|---|
| 4K30 Eevee render | +$0.30–0.60 |
| 4K60 | +$0.75–1.55 |
| Cycles "premium look" render | +$0.75–1.90 |
| 2× SR to 4K, self-hosted | +$0.05–0.20 |
| 2× SR via Topaz API | +$0.80 |
| Experimental diffusion pass (Phase 4C) | +$1–4 |
| Draft preview (three.js) | < $0.05, 1–3 min |

### 13.3 One-time per-course costs

| Item | Cost |
|---|---|
| Data acquisition + processing (all 18 holes share it) | ~$0.10–0.50 compute + ~$1–3/yr storage for course rasters |
| Human verification time (course employee) | The real cost — the editor's UX budget: **< 10 min/hole** fully manual, less with SAM2 assist |
| Premium imagery (only if that tier is chosen) | Maxar archive anchor ~$25/km² ≈ $50–75/course; aerial providers quote-based — TBD at Phase 3 gate |

### 13.4 What this means commercially

Even the most expensive stack (4K60 Cycles + Topaz) lands under ~$5/hole of compute; the standard product is **under $0.50/hole**. At any plausible price point ($50–500/hole or course packages), unit economics are dominated by customer acquisition and support, not compute — meaning we can afford generous regeneration (pin updates, seasonal re-renders) as product features rather than cost centers. The per-stage `timings`/`costs` ledger on every `Render` row keeps this table honest as real data arrives.

---

## 14. What I need from you (product owner)

Only items that materially affect Phase 1, roughly in the order I'll need them:

1. **Brookwood scorecard for Hole 1** — a photo or transcription of the actual scorecard row (par, yardage per tee, tee names). "Approximately 520 yards" is fine to start, but the validation engine should test against the real published number, and I need the back tee's actual name.
2. **The aerial screenshot** — commit-free, reference-only. I will use it solely to orient the manual trace (which direction the hole runs, where bunkers cluster); its pixels never enter the pipeline. If you can't share it, a verbal description of the routing (dogleg direction, water presence) is enough.
3. **One calibration answer when I ask it** — during Phase 1 I will plot the two disputed coordinates on licensed imagery and propose what each actually marks; I'll need you (or someone who knows the course) to confirm the corrected back-tee and green positions in the editor. This is the §11 human gate.
4. **Cloud account decision** — whether to deploy the PoC infrastructure under an account you own (recommended: you hold the keys and the data from day one) or have me prototype locally-only in Phase 1 and defer cloud to Phase 2. Phase 1 is deliberately runnable on a laptop; the decision only becomes blocking at Phase 2 (GPU rendering).
5. **Nothing else yet.** Branding assets, pricing, billing, and premium-imagery budget decisions are intentionally deferred; I'll raise the premium-imagery question with real side-by-side render evidence at the Phase 3 gate, where it can be answered with data instead of speculation.

---

## Appendix A — Key license sources (as researched 2026-08-08)

Data licensing: [Indiana Imagery Program](https://imagery.gio.in.gov/) · [Indiana Elevation Program](https://elevation.gio.in.gov/) · [Indiana imagery on AWS Open Data](https://registry.opendata.aws/in-imagery/) · [Indiana lidar on AWS Open Data](https://registry.opendata.aws/in-elevation/) · [Woolpert 2025–28 program award](https://woolpert.com/news/woolpert-to-collect-orthoimagery-and-lidar-for-state-of-indiana-help-advance-statewide-imagery-and-lidar-programs/) · [NAIP on AWS](https://registry.opendata.aws/naip/) · [Google Map Tiles API policies](https://developers.google.com/maps/documentation/tile/policies) · [Google Maps Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms) · [Google Aerial View API policies](https://developers.google.com/maps/documentation/aerial-view/policies) · [Mapbox Product Terms (2025)](https://cdn.prod.website-files.com/609ed46055e27a02ffc0749b/67fd8d3325f4dfaf2f5145ef_Mapbox%20Product%20Terms%20(2025-04-14).pdf) · [Esri Terms of Use](https://www.esri.com/en-us/legal/terms/web-site-service) · [Nearmap Product-Specific Terms](https://www.nearmap.com/legal/product-specific-terms) · [Vexcel EULA](https://vexceldata.com/eula/) · [Vexcel nationwide 7.5 cm announcement](https://vexceldata.com/stories/vexcel-announces-the-first-nationwide-u-s-aerial-imagery-program-at-7-5cm-resolution/) · [HxGN Content Program FAQ](https://hxgncontent.com/about/faq) · [Maxar ARD license terms](https://www.maxar.com/legal/ARD-license-terms) · [OSMF Licence & Legal FAQ](https://osmfoundation.org/wiki/Licence/Licence_and_Legal_FAQ) · [Copernicus DEM license](https://docs.sentinel-hub.com/api/latest/static/files/data/dem/resources/license/License-COPDEM-30.pdf) · [Cesium content usage guide](https://cesium.com/learn/ion/content-usage-and-attribution-guide/)

Rendering & compute: [CesiumJS (Apache-2.0)](https://github.com/CesiumGS/cesium) · [Cesium ion pricing](https://cesium.com/platform/cesium-ion/pricing/) · [Unreal non-game pricing](https://www.unrealengine.com/blog/we-are-updating-unreal-engine-twinmotion-and-realitycapture-pricing-in-late-april) · [GPU pricing comparison](https://www.cloudzero.com/blog/cloud-gpu-pricing-comparison/) · [Modal pricing](https://modal.com/pricing)

AI models & tools: [Real-ESRGAN license (BSD-3)](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE) · [SAM2 (Apache-2.0)](https://github.com/facebookresearch/sam2) · [VRT/RVRT (CC-BY-NC — excluded)](https://github.com/JingyunLiang/RVRT) · [Topaz EULA (desktop — excluded)](https://topazlabs.com/eula) · [Topaz API](https://www.topazlabs.com/api) · [Topaz video upscale pricing on fal](https://fal.ai/models/fal-ai/topaz/upscale/video) · [Danish Golf Courses Orthophotos dataset](https://www.kaggle.com/datasets/jacotaco/danish-golf-courses-orthophotos) · [OSM golf tagging](https://wiki.openstreetmap.org/wiki/Tag:leisure%3Dgolf_course)
