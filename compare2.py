# compare2.py - DBDAA (paper) vs Enhanced (our test implementation)
import random
from data import DATASETS, TOTAL_RESOURCES, get_available
from dbdaa import dbdaa_run
from enhanced import enhanced_run
from compare import validate_sequence


def average(values):
    return sum(values) / len(values)


def waits(result, arrival):
    """waiting time of process i = time it first starts - its arrival time"""
    n = len(arrival)
    return [result["first_start"][i] - arrival[i] for i in range(n)]


def part_a_paper_data():
    print("=" * 74)
    print("PART A: the paper's datasets (everyone arrives at time 0, aging has no effect)")
    print("=" * 74)
    print("%-10s %-12s %8s %8s %8s %8s %8s %6s" %
          ("Data", "Algorithm", "1st rnd", "total", "finish", "avgwait", "maxwait", "valid"))
    names = ["Data 1", "Data 2", "Data 3"]
    for dname, (maximum, allocation, bt) in zip(names, DATASETS.values()):
        n = len(maximum)
        arrival = [0] * n
        available = get_available(allocation)
        runs = [("DBDAA", dbdaa_run(TOTAL_RESOURCES, maximum, allocation, bt, arrival)),
                ("Enhanced", enhanced_run(TOTAL_RESOURCES, maximum, allocation, bt, arrival))]
        for algo, r in runs:
            w = waits(r, arrival)
            valid = validate_sequence(r["safe_sequence"], available, maximum, allocation)
            print("%-10s %-12s %8d %8d %8d %8.1f %8d %6s" %
                  (dname, algo, r["episodes"][0]["comps"], r["comparisons"],
                   r["end_time"], average(w), max(w), valid))
        print()


def make_stream(rng, n_heavy=4, n_light=40):
    """A stream of small processes arriving steadily, plus a few heavy processes
    that arrive at the start. The processor stays busy, so heavy processes can be
    overtaken again and again (starvation test)."""
    d = 5
    n = n_heavy + n_light
    allocation = [[rng.randint(0, 1) for _ in range(d)] for _ in range(n)]
    avail = [rng.randint(5, 7) for _ in range(d)]
    total = [avail[j] + sum(allocation[i][j] for i in range(n)) for j in range(d)]
    maximum = []
    burst = []
    arrival = []
    for i in range(n):
        heavy = i < n_heavy
        row = []
        for j in range(d):
            if heavy:
                need = rng.randint(8, 12)
            else:
                need = rng.randint(0, 3)
            row.append(min(total[j], allocation[i][j] + need))
        maximum.append(row)
        if heavy:
            burst.append(rng.randint(2, 4))
            arrival.append(0)
        else:
            burst.append(rng.randint(2, 3))
            arrival.append(2 * (i - n_heavy) + rng.randint(0, 1))   # one new process every ~2 units
    return total, maximum, allocation, burst, arrival


def part_b_stream(runs=300, seed=1):
    print("=" * 74)
    print("PART B: steady stream of small processes + 4 heavy ones (starvation test)")
    print("        average over", runs, "random systems, 44 processes each")
    print("=" * 74)
    settings = [("DBDAA (paper)", None)]
    for alpha in (0.0, 0.25, 0.5, 1.0, 2.0):
        settings.append(("Enhanced a=" + str(alpha), alpha))

    rng = random.Random(seed)
    totals = {name: {"comps": [], "avg": [], "max": [], "heavy": [], "finish": []} for name, _ in settings}
    used = 0
    while used < runs:
        total, maximum, allocation, burst, arrival = make_stream(rng)
        n = len(maximum)
        base = dbdaa_run(total, maximum, allocation, burst, arrival)
        if len(base["safe_sequence"]) != n:
            continue                                   # skip systems that are not fully safe
        results = {"DBDAA (paper)": base}
        ok = True
        for name, alpha in settings[1:]:
            r = enhanced_run(total, maximum, allocation, burst, arrival, alpha=alpha)
            if len(r["safe_sequence"]) != n:
                ok = False
            results[name] = r
        if not ok:
            continue
        used += 1
        for name, r in results.items():
            w = waits(r, arrival)
            totals[name]["comps"].append(r["comparisons"])
            totals[name]["avg"].append(average(w))
            totals[name]["max"].append(max(w))
            totals[name]["heavy"].append(average(w[:4]))
            totals[name]["finish"].append(r["end_time"])

    print("%-18s %8s %9s %9s %12s %8s" %
          ("Algorithm", "comps", "avg wait", "max wait", "heavy wait", "finish"))
    for name, _ in settings:
        t = totals[name]
        print("%-18s %8.1f %9.1f %9.1f %12.1f %8.1f" %
              (name, average(t["comps"]), average(t["avg"]), average(t["max"]),
               average(t["heavy"]), average(t["finish"])))


if __name__ == "__main__":
    part_a_paper_data()
    part_b_stream()