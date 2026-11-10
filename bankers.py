# bankers.py - traditional Banker's safety algorithm (Silberschatz style)
from data import DATASETS, get_available


def bankers_safety(available, maximum, allocation):
    n = len(maximum)
    d = len(available)

    # Step 1: Need = Maximum - Allocation
    need = []
    for i in range(n):
        row = []
        for j in range(d):
            row.append(maximum[i][j] - allocation[i][j])
        need.append(row)

    # Step 2: Work = Available, Finish = False
    work = available[:]
    finish = [False] * n
    safe_sequence = []
    comparisons = 0

    # Step 3: repeatedly find a process with Need <= Work
    while True:
        found = False
        for i in range(n):
            if finish[i]:
                continue
            # check Need[i] <= Work for all d resources
            # (d comparisons per check, as counted in the paper's Table 8)
            can_run = True
            for j in range(d):
                comparisons += 1
                if need[i][j] > work[j]:
                    can_run = False
            if can_run:
                # Step 4: pretend to run it, release its resources
                for j in range(d):
                    work[j] += allocation[i][j]
                finish[i] = True
                safe_sequence.append(i + 1)   # P1 -> 1
                found = True
                break                          # restart scan from P1
        if not found:
            break

    # Step 5: safe only if every process finished
    is_safe = all(finish)
    return is_safe, safe_sequence, comparisons


if __name__ == "__main__":
    for name, (maximum, allocation, bt) in DATASETS.items():
        available = get_available(allocation)
        safe, seq, comps = bankers_safety(available, maximum, allocation)
        print(name)
        print("  Available :", available)
        print("  Safe      :", safe)
        print("  Sequence  :", ["P" + str(p) for p in seq])
        print("  Comparisons:", comps)
        print()