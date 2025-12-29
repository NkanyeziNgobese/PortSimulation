# Vessel/Berth Layer (V1) Notes

## What changed
- Added a vessel/berth layer (V1) that can drive container arrivals in batches.
- Added vessel metrics (arrival, berth start/end, anchorage wait, pier, moves per call, TEU estimate).
- Added vessel plots (anchorage wait distribution, berth utilization).
- Added a sanity-check cell for vessels/week, total TEU, and utilization.

## How to run
1) Default mode (unchanged): direct container arrivals  
   - Leave `USE_VESSEL_ARRIVALS = False` in the global parameters cell.
2) Vessel-driven mode (new):  
   - Set `USE_VESSEL_ARRIVALS = True` in the global parameters cell.
   - Optional toggles: `ENABLE_ANCHORAGE_QUEUE`, `INCLUDE_MARINE_DELAYS`.

## Parameters and provenance
Parameters are centralized in `vessel_params.py` with explicit tags:
- SOURCE-ANCHORED: derived from `/mnt/data/pasted.txt` (line refs marked as TBD).
- ASSUMPTION TO TUNE: placeholders until exact data is wired in.

## ASSUMPTION TO TUNE
- `TEU_PER_MOVE` (TEU per container move) until unit-volume TEU data is cleaned.
- `ENABLE_ANCHORAGE_QUEUE` / `INCLUDE_MARINE_DELAYS` toggles.
- `VESSEL_IMPORT_SHARE` (used to scale discharge batch vs total moves per call).

## Next data needed
- Exact line references for all SOURCE-ANCHORED parameters in `/mnt/data/pasted.txt`.
- Annual TEU target for the sanity-check comparison.
- Pier-specific moves-per-call or discharge share if available.
