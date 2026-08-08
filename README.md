# Golf Hole Flyover SaaS

A web SaaS that lets golf course staff generate premium, cinematic 10–12 second drone-style flyover videos of individual holes — built on commercially licensed geographic data, verified hole geometry, and a deterministic rendering pipeline, with AI used only as optional appearance enhancement that can never alter course geometry.

## Status

**Phase 2 (base render) — draft tier complete.** Phase 0 (architecture) and Phase 1 (Brookwood Hole 1 verified geometry) are done. The deterministic camera solver and the CPU draft-tier flyover render are working (`data/brookwood/hole1-flyover-draft.mp4`, byte-reproducible); the Blender/GPU premium tier is the next step and needs serverless GPU infrastructure.

The Phase 0 deliverable is the architecture decision document:

📄 **[docs/PHASE0-ARCHITECTURE.md](docs/PHASE0-ARCHITECTURE.md)**

It covers: product restatement, risk analysis, imagery/terrain licensing research (the load-bearing decision), rendering and AI-enhancement research, recommended stack, data model, geometry-validation design, the Brookwood Golf Club Hole 1 proof-of-concept plan, Phase 1 acceptance criteria, the phased implementation plan, and per-hole cost estimates.

Phase 1 (Brookwood Hole 1 geographic proof of concept) begins after product-owner review of that document.
