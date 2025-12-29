"""
Vessel/Berth parameters (minutes-based).

SOURCE-ANCHORED vs ASSUMPTION TO TUNE tags are explicit.
Line references point to /mnt/data/pasted.txt (not accessible in this environment).
Replace "lines TBD" once the file is available.
"""

# Berth slots
PIER1_BERTHS = 3  # SOURCE-ANCHORED: pasted.txt lines TBD (Pier 1 berth count)
PIER2_BERTHS = 6  # SOURCE-ANCHORED: pasted.txt lines TBD (Pier 2 berth count)

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
SWH_PIER1_MOVES_PER_HOUR = 34  # SOURCE-ANCHORED: pasted.txt lines TBD
SWH_PIER2_MOVES_PER_HOUR = 38  # SOURCE-ANCHORED: pasted.txt lines TBD
GCH_MOVES_PER_HOUR = 16  # SOURCE-ANCHORED: pasted.txt lines TBD

# Derived rates (moves/minute) to keep calculations minute-based.
SWH_PIER1_MOVES_PER_MIN = SWH_PIER1_MOVES_PER_HOUR / 60.0
SWH_PIER2_MOVES_PER_MIN = SWH_PIER2_MOVES_PER_HOUR / 60.0
GCH_MOVES_PER_MIN = GCH_MOVES_PER_HOUR / 60.0

# TEU conversion (placeholder until unit-volume TEU data is wired in)
TEU_PER_MOVE = 1.5  # ASSUMPTION TO TUNE

# Annual TEU target (optional sanity check; set when pasted.txt is available)
ANNUAL_TEU_TARGET_TEU = None  # SOURCE-ANCHORED placeholder: pasted.txt lines TBD
