# data.py - datasets from the DBDAA paper (Tables 2, 3, 4)
# Each process: [Maximum (5 values)], [Allocation (5 values)], burst time

TOTAL_RESOURCES = [20, 25, 30, 35, 30]   # R1..R5
CYCLE_M = 30                              # one cycle (m) used in the paper

# ---------------- Table 2 : best case ----------------
BEST_MAX = [
    [8, 4, 11, 11, 5],     # P1
    [5, 6, 4, 12, 7],      # P2
    [7, 15, 12, 10, 5],    # P3
    [7, 8, 5, 3, 5],       # P4
    [14, 8, 7, 7, 4],      # P5
    [6, 18, 10, 14, 4],    # P6
    [5, 5, 4, 5, 5],       # P7
    [12, 12, 15, 9, 20],   # P8
    [2, 5, 4, 10, 5],      # P9
    [2, 3, 3, 3, 3],       # P10
]
BEST_ALLOC = [
    [4, 2, 3, 4, 2],
    [0, 3, 2, 5, 3],
    [2, 1, 2, 1, 3],
    [1, 5, 3, 2, 2],
    [3, 1, 1, 3, 1],
    [1, 2, 0, 2, 0],
    [3, 2, 1, 3, 4],
    [2, 0, 2, 4, 2],
    [0, 2, 3, 5, 3],
    [0, 2, 3, 2, 2],
]
BEST_BT = [3, 4, 2, 1, 5, 3, 2, 4, 1, 5]

# ---------------- Table 3 : average case ----------------
AVG_MAX = [
    [9, 10, 8, 12, 10],
    [10, 13, 12, 14, 14],
    [12, 9, 10, 9, 8],
    [3, 3, 4, 4, 5],
    [5, 7, 5, 7, 9],
    [6, 4, 5, 6, 2],
    [16, 14, 13, 17, 14],
    [13, 12, 16, 20, 20],
    [12, 14, 14, 13, 16],
    [15, 22, 14, 15, 20],
]
AVG_ALLOC = [
    [2, 4, 2, 2, 2],
    [1, 3, 3, 3, 4],
    [3, 1, 2, 2, 2],
    [1, 1, 1, 1, 0],
    [1, 2, 3, 4, 3],
    [2, 1, 1, 1, 1],
    [1, 2, 4, 5, 4],
    [3, 0, 3, 3, 5],
    [2, 2, 4, 4, 3],
    [0, 4, 4, 2, 0],
]
AVG_BT = [3, 4, 2, 1, 5, 3, 2, 4, 1, 5]

# ---------------- Table 4 : worst case ----------------
WORST_MAX = [
    [15, 16, 17, 19, 18],
    [8, 6, 8, 11, 10],
    [5, 5, 5, 8, 5],
    [9, 8, 14, 18, 15],
    [16, 19, 22, 30, 24],
    [15, 18, 23, 25, 26],
    [6, 7, 10, 12, 11],
    [19, 20, 27, 28, 26],
    [10, 12, 13, 16, 17],
    [17, 17, 19, 26, 22],
]
WORST_ALLOC = [
    [5, 4, 2, 2, 4],
    [2, 2, 3, 4, 2],
    [4, 3, 2, 4, 3],
    [1, 1, 1, 3, 2],
    [0, 2, 2, 4, 0],
    [0, 2, 3, 2, 4],
    [1, 1, 1, 3, 3],
    [2, 3, 4, 3, 2],
    [1, 4, 3, 0, 3],
    [2, 1, 2, 2, 2],
]
WORST_BT = [3, 4, 2, 1, 5, 3, 2, 4, 1, 5]

DATASETS = {
    "Table 2 (best)":    (BEST_MAX,  BEST_ALLOC,  BEST_BT),
    "Table 3 (average)": (AVG_MAX,   AVG_ALLOC,   AVG_BT),
    "Table 4 (worst)":   (WORST_MAX, WORST_ALLOC, WORST_BT),
}


def get_available(allocation):
    """Available = Total - sum of allocations (same as paper Eq. 2)."""
    d = len(TOTAL_RESOURCES)
    available = []
    for j in range(d):
        used = 0
        for row in allocation:
            used += row[j]
        available.append(TOTAL_RESOURCES[j] - used)
    return available