"""
Vessel/Berth parameters (minutes-based).

Assumption tags are explicit. The source file referenced in earlier notes is
missing from this repo, so any previous "SOURCE-ANCHORED" tags are treated as
assumptions until sources exist.
"""

# Berth slots + crane pools
PIER1_BERTHS = 2  # ASSUMPTION (source missing from repo): Pier 1 berth capacity
PIER2_BERTHS = 4  # ASSUMPTION (source missing from repo): Pier 2 berth capacity

PIER1_CRANE_POOL = 7   # ASSUMPTION TO TUNE (source missing from repo)
PIER2_CRANE_POOL = 15  # ASSUMPTION TO TUNE (source missing from repo)

MIN_CRANES_PER_VESSEL = 2  # ASSUMPTION (source missing from repo): gang minimum

# Crane assignment distributions (gang intensity)
# ASSUMPTION (source missing from repo): pier-specific gang distributions
PIER1_GANG_DISTRIBUTION = {2: 0.25, 3: 0.55, 4: 0.20}
PIER2_GANG_TRIANGULAR = (2, 4, 6)  # min, mode, max

# Vessel arrivals
VESSEL_INTERARRIVAL_MEAN_MINS = 1053  # ASSUMPTION (source missing from repo): mean interarrival

# Marine service delays (simple, togglable in notebook)
PILOTAGE_AND_BERTHING_TIME_MINS = 120  # ASSUMPTION (source missing from repo)
SAILING_CLEARANCE_WINDOW_MINS = 60  # ASSUMPTION (source missing from repo)

# Anchorage waiting target
ANCHORAGE_WAIT_MEAN_MINS = 2880  # ASSUMPTION (source missing from repo): baseline mean

# Moves per call
AVG_MOVES_PER_CALL = 2433  # ASSUMPTION (source missing from repo): avg moves/call

# Productivity references (moves/hour)
SWH_PIER1_MOVES_PER_HOUR = 39  # ASSUMPTION (source missing from repo)
SWH_PIER2_MOVES_PER_HOUR = 43  # ASSUMPTION (source missing from repo)
GCH_MOVES_PER_HOUR = 18  # ASSUMPTION (source missing from repo)

# Derived rates (moves/minute) to keep calculations minute-based.
SWH_PIER1_MOVES_PER_MIN = SWH_PIER1_MOVES_PER_HOUR / 60.0
SWH_PIER2_MOVES_PER_MIN = SWH_PIER2_MOVES_PER_HOUR / 60.0
GCH_MOVES_PER_MIN = GCH_MOVES_PER_HOUR / 60.0

# Effective working time and shift-change loss
# NOTE: Keep SHIFT_LENGTH_MINS aligned with the notebook shift calendar.
SHIFT_LENGTH_MINS = 720  # ASSUMPTION (source missing from repo): 12-hour shifts
NET_EFFECTIVE_WORK_HOURS_PER_DAY = 21.83  # ASSUMPTION (source missing from repo)
NET_EFFECTIVE_WORK_FACTOR = NET_EFFECTIVE_WORK_HOURS_PER_DAY / 24.0

# Shift change hook time loss per crane (minutes).
SHIFT_CHANGE_HOOK_TIME_MIN = 30  # ASSUMPTION (source missing from repo)
SHIFT_CHANGE_HOOK_TIME_MAX = 60  # ASSUMPTION (source missing from repo)

# Pier efficiency factors (horizontal transport + operational friction).
PIER1_EFFICIENCY_FACTOR = 0.90  # ASSUMPTION TO TUNE (Pier 1 relatively stable)
PIER2_EFFICIENCY_FACTOR = 0.75  # ASSUMPTION TO TUNE (Pier 2 constrained by availability)

# TEU conversion (placeholder until unit-volume TEU data is wired in)
TEU_PER_MOVE = 1.5  # ASSUMPTION TO TUNE

# Annual TEU target (optional sanity check; set when pasted.txt is available)
ANNUAL_TEU_TARGET_TEU = None  # ASSUMPTION (source missing from repo)
