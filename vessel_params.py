"""
Vessel/Berth parameters (minutes-based).

SOURCE-ANCHORED vs ASSUMPTION TO TUNE tags are explicit.
Line references point to /mnt/data/pasted.txt (not accessible in this environment).
Replace "lines TBD" once the file is available.
"""

# Berth slots + crane pools
PIER1_BERTHS = 2  # SOURCE-ANCHORED: pasted.txt lines TBD (Pier 1 berth capacity)
PIER2_BERTHS = 4  # SOURCE-ANCHORED: pasted.txt lines TBD (Pier 2 berth capacity)

PIER1_CRANE_POOL = 7   # ASSUMPTION TO TUNE (set from pasted.txt if available)
PIER2_CRANE_POOL = 15  # ASSUMPTION TO TUNE (set from pasted.txt if available)

MIN_CRANES_PER_VESSEL = 2  # SOURCE-ANCHORED placeholder (gang minimum)

# Crane assignment distributions (gang intensity)
# SOURCE-ANCHORED: pasted.txt lines TBD (pier-specific gang distributions)
PIER1_GANG_DISTRIBUTION = {2: 0.25, 3: 0.55, 4: 0.20}
PIER2_GANG_TRIANGULAR = (2, 4, 6)  # min, mode, max

# Vessel arrivals
VESSEL_INTERARRIVAL_MEAN_MINS = 1053  # SOURCE-ANCHORED: pasted.txt lines TBD (mean interarrival)

# Marine service delays (simple, togglable in notebook)
PILOTAGE_AND_BERTHING_TIME_MINS = 120  # SOURCE-ANCHORED: pasted.txt lines TBD
SAILING_CLEARANCE_WINDOW_MINS = 60  # SOURCE-ANCHORED: pasted.txt lines TBD

# Anchorage waiting target
ANCHORAGE_WAIT_MEAN_MINS = 2880  # SOURCE-ANCHORED: pasted.txt lines TBD (baseline mean)

# Moves per call
AVG_MOVES_PER_CALL = 2433  # SOURCE-ANCHORED: pasted.txt lines TBD (avg moves/call)

# Productivity references (moves/hour)
SWH_PIER1_MOVES_PER_HOUR = 39  # SOURCE-ANCHORED: pasted.txt lines TBD
SWH_PIER2_MOVES_PER_HOUR = 43  # SOURCE-ANCHORED: pasted.txt lines TBD
GCH_MOVES_PER_HOUR = 18  # SOURCE-ANCHORED: pasted.txt lines TBD

# Derived rates (moves/minute) to keep calculations minute-based.
SWH_PIER1_MOVES_PER_MIN = SWH_PIER1_MOVES_PER_HOUR / 60.0
SWH_PIER2_MOVES_PER_MIN = SWH_PIER2_MOVES_PER_HOUR / 60.0
GCH_MOVES_PER_MIN = GCH_MOVES_PER_HOUR / 60.0

# Effective working time and shift-change loss
# NOTE: Keep SHIFT_LENGTH_MINS aligned with the notebook shift calendar.
SHIFT_LENGTH_MINS = 720  # SOURCE-ANCHORED placeholder (12-hour shifts)
NET_EFFECTIVE_WORK_HOURS_PER_DAY = 21.83  # SOURCE-ANCHORED: pasted.txt lines TBD
NET_EFFECTIVE_WORK_FACTOR = NET_EFFECTIVE_WORK_HOURS_PER_DAY / 24.0

# Shift change hook time loss per crane (minutes).
SHIFT_CHANGE_HOOK_TIME_MIN = 30  # SOURCE-ANCHORED: pasted.txt lines TBD
SHIFT_CHANGE_HOOK_TIME_MAX = 60  # SOURCE-ANCHORED: pasted.txt lines TBD

# Pier efficiency factors (horizontal transport + operational friction).
PIER1_EFFICIENCY_FACTOR = 0.90  # ASSUMPTION TO TUNE (Pier 1 relatively stable)
PIER2_EFFICIENCY_FACTOR = 0.75  # ASSUMPTION TO TUNE (Pier 2 constrained by availability)

# TEU conversion (placeholder until unit-volume TEU data is wired in)
TEU_PER_MOVE = 1.5  # ASSUMPTION TO TUNE

# Annual TEU target (optional sanity check; set when pasted.txt is available)
ANNUAL_TEU_TARGET_TEU = None  # SOURCE-ANCHORED placeholder: pasted.txt lines TBD
