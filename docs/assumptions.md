# Assumptions Register

This register lists assumptions found in code and docs. It does not introduce new sources.

## Demo (CLI) assumptions

- The demo uses synthetic arrivals and scaled timings to finish quickly.
- Flow mix defaults to IMPORT 60%, EXPORT 20%, TRANSSHIP 20%.
- Yard move time uses a triangular distribution with congestion penalty (see `src/sim/model.py`).
- Import dwell is a banded distribution plus a small post-discharge offset.
- Export dwell is a uniform placeholder.
- Truck pickup logic tries to fill a 2-TEU truck with either a 40ft or two 20ft containers.

## Notebook model assumptions (selected)

- Yard move times use a triangular distribution with congestion penalties (`YARD_OCC_THRESHOLD`, `REHANDLE_ALPHA`).
- Import dwell uses banded distributions and a 24-hour post-discharge offset.
- Export dwell uses a uniform placeholder when vessel schedules are not modeled.
- Vessel layer parameters are tagged as assumptions or sources; many are placeholders pending source confirmation.
- Customs holds and rebooking logic are described in notes/helpers but are not wired into the main container flow yet.

## Source gaps and provenance notes

- `vessel_params.py` and `VESSEL_LAYER_NOTES.md` previously referenced `/mnt/data/pasted.txt`. That file is not in this repo, so those parameters must be treated as assumptions until sources are provided.
- The CLI demo does not claim any source anchoring; it is purely synthetic for reviewer convenience.
