# Vessel/Berth Layer (Phase 2) Notes

## What changed
- Added gang assignment (cranes per vessel) with pier-specific distributions.
- Added crane pools per pier and recorded crane-pool empty time.
- Switched to rate-based discharge (GCH * cranes * efficiency) and post-discharge container entry.
- Added vessel metrics (cranes requested/assigned, crane wait, efficiency used, shift-loss minutes).
- Added vessel plots (anchorage wait, cranes assigned by pier, berth utilization).
- Expanded sanity checks (SWH vs reference, crane pool empty %, anchorage wait).

## How to run
1) Default mode (unchanged): direct container arrivals  
   - Leave `USE_VESSEL_LAYER = False` in the global parameters cell.
2) Vessel-driven mode (Phase 2):  
   - Set `USE_VESSEL_LAYER = True` in the global parameters cell.
   - Optional toggles: `ENABLE_ANCHORAGE_QUEUE`, `INCLUDE_MARINE_DELAYS`.

## Parameters and provenance
Parameters are centralized in `vessel_params.py` with explicit tags:
- ASSUMPTION (source missing from repo): values that previously referenced a missing source file.
- ASSUMPTION TO TUNE: placeholders until exact data is wired in.

## ASSUMPTION TO TUNE
- `TEU_PER_MOVE` (TEU per container move) until unit-volume TEU data is cleaned.
- `ENABLE_ANCHORAGE_QUEUE` / `INCLUDE_MARINE_DELAYS` toggles.
- `VESSEL_IMPORT_SHARE` (used to scale discharge batch vs total moves per call).
- Pier efficiency factors and crane pool sizes if not in the source notes.
- Shift-loss aggregation approach (hook loss applied as added downtime).

## Next data needed
- The missing source file or citations that justify berth, crane pool, and productivity parameters.
- Annual TEU target for the sanity-check comparison.
- Pier-specific moves-per-call or discharge share if available.
