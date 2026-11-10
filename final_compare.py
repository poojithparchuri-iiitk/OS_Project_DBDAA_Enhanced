# final_compare.py - all final experiments for the report, in one place
#   Part 1: the paper's datasets (Data 1, 2, 3)
#   Part 2: scale test - comparisons as the number of processes grows
#   Part 3: random systems with staggered arrivals, from very tight to loose
#   Part 4: starvation test (steady stream of small processes + heavy ones)
#   Part 5: sensitivity of the settings we chose
#
# Variants:
#   DBDAA (cycle)       : the paper's algorithm, parked processes wait for the 30-unit cycle
#   DBDAA (idle retry)  : the paper's algorithm, parked processes retried as soon as the
#                         ready queue is empty (second reading of the paper) = fair baseline
#   Enhanced            : our Modification 1 (adaptive check) + 2 (gated aging, 'overtaken >= 5')
#   Enhanced + idle     : Modifications 1 + 2 + idle retry
import math
import random
import enhanced
from data import DATASETS, TOTAL_RESOURCES, get_available
from bankers import bankers_safety
from dbdaa import dbdaa_run
from enhanced import enhanced_run, enhanced_final, enhanced_final_idle
from compare import validate_sequence, bankers_times, average
from compare2 import make_stream


def make_system(rng, n, slack, spread):
    """Random system that is safe by construction.
    slack small = tight resources, slack large = loose resources.
    spread = latest arrival time (0 = everyone arrives at time 0)."""
    d = 5
    allocation = [[rng.randint(0, 2) for _ in range(d)] for _ in range(n)]
    avail = [rng.randint(1, 3) for _ in range(d)]
    order = list(range(n))
    rng.shuffle(order)
    work = avail[:]
    need = [None] * n
    for i in order:
        need[i] = [max(0, work[j] - rng.randint(0, slack)) for j in range(d)]
        for j in range(d):
            work[j] += allocation[i][j]
    total = [avail[j] + sum(allocation[i][j] for i in range(n)) for j in range(d)]
    maximum = [[allocation[i][j] + need[i][j] for j in range(d)] for i in range(n)]
    burst = [rng.randint(1, 6) for _ in range(n)]
    arrival = [0] * (n // 3) + [rng.randint(0, spread) for _ in range(n - n // 3)]
    return total, maximum, allocation, burst, arrival


def good_systems(count, n, slack, spread, seed):
    """Generate 'count' systems that DBDAA can fully finish."""
    rng = random.Random(seed)
    systems = []
    while len(systems) < count:
        s = make_system(rng, n, slack, spread)
        r = dbdaa_run(*s)
        if len(r["safe_sequence"]) == n:
            systems.append(s)
    return systems


def measure(systems, run_fn):
    """Returns averages of: comparisons, avg wait, max wait, heavy wait (first 4
    processes), finish time. Stops with an error if a run does not finish every process."""
    c = []
    a = []
    m = []
    h = []
    f = []
    for total, maximum, allocation, burst, arrival in systems:
        n = len(maximum)
        r = run_fn(total, maximum, allocation, burst, arrival)
        assert len(r["safe_sequence"]) == n, "a run did not finish all processes"
        w = [r["first_start"][i] - arrival[i] for i in range(n)]
        c.append(r["comparisons"])
        a.append(average(w))
        m.append(max(w))
        h.append(average(w[:4]))
        f.append(r["end_time"])
    return average(c), average(a), average(m), average(h), average(f)


def paired_summary(systems, base_fn, new_fn):
    """Per-system difference in comparisons (new - base): mean, 95% confidence interval,
    and in how many systems 'new' was better / worse / equal."""
    diffs = []
    better = worse = equal = 0
    for s in systems:
        d = new_fn(*s)["comparisons"] - base_fn(*s)["comparisons"]
        diffs.append(d)
        if d < 0:
            better += 1
        elif d > 0:
            worse += 1
        else:
            equal += 1
    mean = average(diffs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (len(diffs) - 1))
    return mean, 1.96 * sd / math.sqrt(len(diffs)), better, worse, equal


IDLE = lambda *s: dbdaa_run(*s, wait_for_cycle=False)


# ---------------------------------------------------------------- Part 1
def part1():
    print("=" * 88)
    print("PART 1: the paper's datasets (everyone arrives at time 0)")
    print("=" * 88)
    print("%-7s %-22s %8s %7s %7s %9s %6s" %
          ("Data", "Algorithm", "1st rnd", "total", "finish", "avg wait", "valid"))
    variants = [("DBDAA (cycle)", dbdaa_run),
                ("DBDAA (idle retry)", IDLE),
                ("Enhanced (cycle)", enhanced_final),
                ("Enhanced + idle", enhanced_final_idle)]
    for dname, (maximum, allocation, bt) in zip(["Data 1", "Data 2", "Data 3"], DATASETS.values()):
        n = len(maximum)
        arrival = [0] * n
        available = get_available(allocation)

        safe, seq, comps = bankers_safety(available, maximum, allocation)
        start, finish, end = bankers_times(seq, bt)
        valid = validate_sequence(seq, available, maximum, allocation)
        print("%-7s %-22s %8d %7d %7d %9.1f %6s" %
              (dname, "Traditional", comps, comps, end, average([start[p] for p in seq]), valid))

        for name, fn in variants:
            r = fn(TOTAL_RESOURCES, maximum, allocation, bt, arrival)
            valid = validate_sequence(r["safe_sequence"], available, maximum, allocation)
            print("%-7s %-22s %8d %7d %7d %9.1f %6s" %
                  (dname, name, r["episodes"][0]["comps"], r["comparisons"], r["end_time"],
                   average(r["first_start"]), valid))
        print()


# ---------------------------------------------------------------- Part 2
def part2(runs=15):
    print("=" * 88)
    print("PART 2: scale test - comparisons as the number of processes grows (all arrive at 0)")
    print("        'Old gate' = first version of aging (waited >= 30); 'Enhanced' = final version")
    print("=" * 88)
    for label, slack in (("tight systems", 3), ("loose systems", 12)):
        print("\n" + label)
        print("%6s %12s %9s %16s %10s %10s" %
              ("n", "Traditional", "DBDAA", "Enhanced(check)", "Old gate", "Enhanced"))
        for n in (10, 25, 50, 100, 200):
            rng = random.Random(n + slack)
            cols = {"t": [], "d": [], "c": [], "o": [], "e": []}
            while len(cols["t"]) < runs:
                total, maximum, allocation, burst, arrival = make_system(rng, n, slack, 0)
                arrival = [0] * n
                available = [total[j] - sum(allocation[i][j] for i in range(n)) for j in range(5)]
                safe, seq, c = bankers_safety(available, maximum, allocation)
                s = (total, maximum, allocation, burst, arrival)
                rd = dbdaa_run(*s)
                rc = enhanced_run(*s, adaptive=True)
                ro = enhanced_run(*s, adaptive=True, gate_wait=30, probe_gap=5)
                re = enhanced_final(*s)
                if not safe or any(len(r["safe_sequence"]) != n for r in (rd, rc, ro, re)):
                    continue
                cols["t"].append(c)
                cols["d"].append(rd["comparisons"])
                cols["c"].append(rc["comparisons"])
                cols["o"].append(ro["comparisons"])
                cols["e"].append(re["comparisons"])
            print("%6d %12.0f %9.0f %16.0f %10.0f %10.0f" %
                  (n, average(cols["t"]), average(cols["d"]), average(cols["c"]),
                   average(cols["o"]), average(cols["e"])))


# ---------------------------------------------------------------- Part 3 and 4
CONFIGS = [
    ("DBDAA (cycle)", lambda *s: dbdaa_run(*s)),
    ("DBDAA (idle retry)", IDLE),
    ("Check only + idle", lambda *s: enhanced_run(*s, adaptive=True, wait_for_cycle=False)),
    ("Naive aging + idle", lambda *s: enhanced_run(*s, adaptive=False, alpha=0.5, wait_for_cycle=False)),
    ("Old gate + idle", lambda *s: enhanced_run(*s, adaptive=True, gate_wait=30, probe_gap=5,
                                                wait_for_cycle=False)),
    ("Enhanced + idle", lambda *s: enhanced_final_idle(*s)),
]


def part3(runs=200, n=30):
    print()
    print("=" * 88)
    print("PART 3: random systems, staggered arrivals (n = %d, %d systems per table)" % (n, runs))
    print("        'Naive aging' and 'Old gate' are our first attempts, shown for the record")
    print("=" * 88)
    for label, slack in (("very tight", 1), ("tight", 3), ("slightly tight", 6), ("loose", 12)):
        systems = good_systems(runs, n, slack, 40, slack * 11)
        print("\n%s" % label)
        print("%-22s %8s %9s %9s %8s" % ("Algorithm", "comps", "avg wait", "max wait", "finish"))
        for name, fn in CONFIGS:
            c, a, m, h, f = measure(systems, fn)
            print("%-22s %8.1f %9.1f %9.1f %8.1f" % (name, c, a, m, f))
        mean, ci, b, w, e = paired_summary(systems, IDLE, lambda *s: enhanced_final_idle(*s))
        print("Enhanced + idle vs DBDAA (idle retry), per system: %+.1f +- %.1f comparisons "
              "(better in %d, worse in %d, equal in %d systems)" % (mean, ci, b, w, e))


def part4(runs=300):
    print()
    print("=" * 88)
    print("PART 4: starvation test - 4 heavy processes + 40 small ones arriving steadily")
    print("        (%d runs; resources are loose here)" % runs)
    print("=" * 88)
    rng = random.Random(1)
    systems = []
    while len(systems) < runs:
        s = make_stream(rng)
        r = dbdaa_run(*s)
        if len(r["safe_sequence"]) == len(s[1]):
            systems.append(s)
    print("%-22s %8s %9s %9s %11s %8s" %
          ("Algorithm", "comps", "avg wait", "max wait", "heavy wait", "finish"))
    for name, fn in CONFIGS:
        c, a, m, h, f = measure(systems, fn)
        print("%-22s %8.1f %9.1f %9.1f %11.1f %8.1f" % (name, c, a, m, h, f))


# ---------------------------------------------------------------- Part 5
def part5():
    print()
    print("=" * 88)
    print("PART 5: sensitivity of the chosen settings")
    print("=" * 88)

    # 5a: adaptive check settings (streak_limit, probe_every)
    scenarios = []
    mx, al, bt = DATASETS["Table 4 (worst)"]
    scenarios.append(("Data 3", [(TOTAL_RESOURCES, mx, al, bt, [0] * 10)]))
    for label, slack in (("very tight", 1), ("tight", 3), ("slightly tight", 6), ("loose", 12)):
        scenarios.append((label, good_systems(150, 20, slack, 0, 500 + slack)))

    base = {}
    for name, systems in scenarios:
        base[name] = measure(systems, dbdaa_run)[0]
    print("\n5a. Adaptive check: change in comparisons vs DBDAA, for (streak_limit, probe_every)")
    print("%-10s" % "setting" + "".join("%-15s" % name for name, _ in scenarios))
    original = enhanced.AdaptiveChecker
    for sl in (1, 2, 3):
        for pe in (1, 2, 4):
            enhanced.AdaptiveChecker = lambda sl=sl, pe=pe: original(streak_limit=sl, probe_every=pe)
            row = "(%d,%d)%s" % (sl, pe, " " * 5)
            for name, systems in scenarios:
                c = measure(systems, lambda *s: enhanced_run(*s, adaptive=True))[0]
                row += "%-15s" % ("%+.1f%%" % (100.0 * (c - base[name]) / base[name]))
            print(row + ("   <- chosen" if (sl, pe) == (2, 4) else ""))
    enhanced.AdaptiveChecker = original

    # 5b: gated aging settings (overtake_limit, probe_gap)
    rng = random.Random(1)
    streams = []
    while len(streams) < 150:
        s = make_stream(rng)
        r = dbdaa_run(*s)
        if len(r["safe_sequence"]) == len(s[1]):
            streams.append(s)
    tight = good_systems(100, 30, 3, 40, 11)
    b_stream = measure(streams, IDLE)
    b_tight = measure(tight, IDLE)
    print("\n5b. Gated aging: (overtake_limit, probe_gap)")
    print("    DBDAA (idle retry) reference: heavy wait %.1f, max wait %.1f | tight systems comps %.1f"
          % (b_stream[3], b_stream[2], b_tight[0]))
    print("%-12s %12s %10s %20s" % ("setting", "heavy wait", "max wait", "tight systems comps"))
    for k in (3, 5, 10, 20):
        for gap in (1, 5, 10):
            fn = lambda *s, k=k, gap=gap: enhanced_run(*s, adaptive=False, overtake_limit=k,
                                                       probe_gap=gap, wait_for_cycle=False)
            st = measure(streams, fn)
            ti = measure(tight, fn)
            print("(%2d,%2d)%s %12.1f %10.1f %20.1f%s" %
                  (k, gap, " " * 4, st[3], st[2], ti[0],
                   "   <- chosen" if (k, gap) == (5, 5) else ""))


if __name__ == "__main__":
    part1()
    part2()
    part3()
    part4()
    part5()