# stress_tests.py - correctness and robustness tests for the whole project
# Run:  python stress_tests.py        (a few seconds; prints PASS / FAIL for each test)
#
#   Test 1: reproduces the paper's numbers (Table 8, Tables 5-7, Figs 3-5)
#   Test 2: the DBDAA check gives exactly the same verdict as the plain check (d = 1..10)
#   Test 3: independent replay of every simulation (a process only runs when its need fits)
#   Test 4: all variants agree with the traditional Banker's algorithm on static systems
#   Test 5: no variant loops forever (stuck system + late arrival)
#   Test 6: measurement - sorting comparisons (the paper does not count them)
import functools
import random
import sys
import threading
import types

from data import DATASETS, TOTAL_RESOURCES, get_available
from bankers import bankers_safety
from dbdaa import dbdaa_run, safety_check
from enhanced import (AdaptiveChecker, enhanced_run, enhanced_final, enhanced_final_idle)

VARIANTS = [
    ("DBDAA (cycle)",         lambda *s: dbdaa_run(*s)),
    ("DBDAA (idle retry)",    lambda *s: dbdaa_run(*s, wait_for_cycle=False)),
    ("Enhanced (cycle)",      lambda *s: enhanced_final(*s)),
    ("Enhanced + idle",       lambda *s: enhanced_final_idle(*s)),
    ("Enhanced, overtake=1",  lambda *s: enhanced_run(*s, adaptive=True, overtake_limit=1,
                                                      probe_gap=1, wait_for_cycle=False)),
]
failures = 0


def report(name, ok, detail=""):
    global failures
    if not ok:
        failures += 1
    print("%-6s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def random_system(rng, n, d, tight, spread, oversize):
    allocation = [[rng.randint(0, 2) for _ in range(d)] for _ in range(n)]
    avail = [rng.randint(0, 3) for _ in range(d)]
    total = [avail[j] + sum(allocation[i][j] for i in range(n)) for j in range(d)]
    maximum = [[min(total[j] + (3 if rng.random() < oversize else 0),
                    allocation[i][j] + rng.randint(0, tight)) for j in range(d)] for i in range(n)]
    burst = [rng.randint(1, 6) for _ in range(n)]
    arrival = [rng.randint(0, spread) for _ in range(n)]
    return total, maximum, allocation, burst, arrival


# ------------------------------------------------------------------ Test 1
def test1_paper_numbers():
    print("\nTest 1: the paper's numbers")
    expect_trad = [85, 100, 125]
    expect_dbdaa_first = [10, 36, 70]
    expect_first_end = [30, 26, 23]
    expect_seq = [
        [7, 1, 2, 4, 3, 5, 6, 8, 9, 10],
        [4, 5, 6, 1, 2, 3, 8, 7, 9, 10],
        [3, 2, 7, 4, 9, 1, 10, 5, 6, 8],
    ]
    expect_dbdaa_safe = [
        [10, 7, 9, 4, 2, 1, 5, 3, 6, 8],
        [4, 6, 5, 1, 2, 9, 8, 10],
        [3, 2, 7, 4, 9, 1, 10, 5],
    ]
    expect_primary = [[], [3, 7], [6, 8]]
    for k, (name, (maximum, allocation, bt)) in enumerate(DATASETS.items()):
        safe, seq, comps = bankers_safety(get_available(allocation), maximum, allocation)
        report("traditional, %s: %d comparisons, paper's safe sequence" % (name, expect_trad[k]),
               safe and comps == expect_trad[k] and seq == expect_seq[k])
        r = dbdaa_run(TOTAL_RESOURCES, maximum, allocation, bt, [0] * len(maximum))
        ep = r["episodes"][0]
        report("DBDAA, %s: first round %d comparisons, sequences, ends at %d" %
               (name, expect_dbdaa_first[k], expect_first_end[k]),
               ep["comps"] == expect_dbdaa_first[k] and ep["safe"] == expect_dbdaa_safe[k]
               and ep["primary"] == expect_primary[k] and ep["end"] == expect_first_end[k])


# ------------------------------------------------------------------ Test 2
def test2_check_exact(per_d=20000):
    print("\nTest 2: the DBDAA check is exact (same verdict as the plain check)")
    rng = random.Random(1)
    for d in (1, 2, 3, 4, 5, 6, 7, 8, 10):
        wrong = 0
        for _ in range(per_d):
            hi = rng.choice([2, 4, 8, 15])
            need = [rng.randint(0, hi) for _ in range(d)]
            avail = [rng.randint(0, hi) for _ in range(d)]
            ok, c = safety_check(need, avail)
            if ok != all(need[j] <= avail[j] for j in range(d)):
                wrong += 1
        report("safety_check, d = %d, %d random vectors" % (d, per_d), wrong == 0, "(wrong: %d)" % wrong)
    wrong = 0
    for d in (2, 3, 5, 8):
        checker = AdaptiveChecker()
        for _ in range(per_d):
            hi = rng.choice([3, 6, 12])
            need = [rng.randint(0, hi) for _ in range(d)]
            avail = [rng.randint(0, hi) for _ in range(d)]
            ok, c = checker.check(need, avail)
            if ok != all(need[j] <= avail[j] for j in range(d)):
                wrong += 1
    report("AdaptiveChecker while switching modes, %d checks" % (4 * per_d), wrong == 0, "(wrong: %d)" % wrong)


# ------------------------------------------------------------------ Test 3
def replay_problems(total, maximum, allocation, burst, arrival, r):
    """Independent replay of the timeline; returns a set of problems found."""
    n = len(maximum)
    d = len(total)
    problems = set()
    tl = sorted(r["timeline"], key=lambda t: t[1])
    ran = [p for p, s, e in tl]
    if len(ran) != len(set(ran)):
        problems.add("a process ran twice")
    for k in range(1, len(tl)):
        if tl[k][1] < tl[k - 1][2]:
            problems.add("two processes overlap on the single processor")
    too_big = set(i for i in range(n) if any(maximum[i][j] > total[j] for j in range(d)))
    finish_of = {p - 1: e for p, s, e in tl}
    for p, s, e in tl:
        i = p - 1
        if i in too_big:
            problems.add("an oversized process ran")
        if s < arrival[i]:
            problems.add("a process started before it arrived")
        if e - s != burst[i]:
            problems.add("wrong run length")
        held = [0] * d
        for q in range(n):
            if q in too_big or arrival[q] > s:
                continue
            if q in finish_of and finish_of[q] <= s:
                continue
            for j in range(d):
                held[j] += allocation[q][j]
        for j in range(d):
            if maximum[i][j] - allocation[i][j] > total[j] - held[j]:
                problems.add("a process ran although its need did not fit")
                break
    if set(r["unsafe_sequence"]) != set(i + 1 for i in too_big):
        problems.add("Unsafe_Sequence is wrong")
    if set(ran) | set(r["stuck"]) | set(r["unsafe_sequence"]) != set(range(1, n + 1)):
        problems.add("a process is neither finished nor reported")
    return problems


def test3_replay(systems=1500):
    print("\nTest 3: independent replay of %d random systems x %d variants" % (systems, len(VARIANTS)))
    rng = random.Random(2024)
    found = {name: set() for name, _ in VARIANTS}
    stuck_systems = 0
    for _ in range(systems):
        n = rng.choice([4, 8, 15, 25, 40])
        d = rng.choice([2, 3, 5, 8])
        s = random_system(rng, n, d, rng.choice([2, 4, 8]), rng.choice([0, 20, 60]), rng.choice([0, 0, 0.1]))
        any_stuck = False
        for name, fn in VARIANTS:
            r = fn(*s)
            found[name] |= replay_problems(*s, r)
            any_stuck = any_stuck or bool(r["stuck"])
        stuck_systems += any_stuck
    print("       (%d of the systems contain processes that can never finish)" % stuck_systems)
    for name, _ in VARIANTS:
        report("replay, " + name, not found[name], str(sorted(found[name])) if found[name] else "")


# ------------------------------------------------------------------ Test 4
def test4_verdicts(systems=2500):
    print("\nTest 4: verdict agrees with the traditional Banker's algorithm (static systems)")
    rng = random.Random(7)
    wrong = {name: 0 for name, _ in VARIANTS}
    safe_count = 0
    for _ in range(systems):
        n = rng.choice([4, 8, 15, 25])
        d = rng.choice([2, 3, 5, 8])
        total, maximum, allocation, burst, _a = random_system(rng, n, d, rng.choice([2, 4, 8]), 0, 0)
        arrival = [0] * n
        available = [total[j] - sum(allocation[i][j] for i in range(n)) for j in range(d)]
        safe, seq, c = bankers_safety(available, maximum, allocation)
        safe_count += safe
        for name, fn in VARIANTS:
            r = fn(total, maximum, allocation, burst, arrival)
            finished_all = len(r["safe_sequence"]) == n
            if finished_all != safe:
                wrong[name] += 1
    print("       (%d of %d systems are safe, the rest are unsafe)" % (safe_count, systems))
    for name, _ in VARIANTS:
        report("verdict, " + name, wrong[name] == 0, "(disagreements: %d)" % wrong[name])


# ------------------------------------------------------------------ Test 5
def test5_no_hang(timeout=5):
    print("\nTest 5: no variant loops forever")
    # two processes that can never run, and a third one that arrives much later
    total = [4, 4]
    maximum = [[4, 4], [4, 4], [1, 1]]
    allocation = [[2, 2], [2, 2], [0, 0]]
    burst = [2, 2, 1]
    arrival = [0, 0, 100]
    for name, fn in VARIANTS:
        box = {}
        t = threading.Thread(target=lambda: box.setdefault("r", fn(total, maximum, allocation, burst, arrival)),
                             daemon=True)
        t.start()
        t.join(timeout)
        report("terminates, " + name, "r" in box)


# ------------------------------------------------------------------ Test 6
class CountingList(list):
    """A list whose sort() counts the comparisons it makes."""
    comparisons = 0

    def sort(self, key=None, reverse=False):
        keys = [key(x) if key else x for x in self]
        order = list(range(len(self)))

        def compare(a, b):
            CountingList.comparisons += 1
            return (keys[a] > keys[b]) - (keys[a] < keys[b])
        order.sort(key=functools.cmp_to_key(compare))
        self[:] = [self[i] for i in order]


def load_counting(filename, modname, extra=None):
    source = open(filename).read()
    assert "ready_queue = []" in source, "cannot instrument " + filename
    source = source.replace("ready_queue = []", "ready_queue = CountingList()")
    if extra:
        source = source.replace(*extra)
    module = types.ModuleType(modname)
    module.CountingList = CountingList
    exec(compile(source, filename, "exec"), module.__dict__)
    return module


def test6_sorting_cost():
    print("\nTest 6: measurement - sorting comparisons (not counted by the paper), average per run")
    from final_compare import good_systems
    dbd = load_counting("dbdaa.py", "dbdaa_counting")
    sys.modules["dbdaa_counting"] = dbd
    enh = load_counting("enhanced.py", "enhanced_counting", ("from dbdaa import", "from dbdaa_counting import"))

    def sort_cost(fn, systems):
        total = 0
        for s in systems:
            CountingList.comparisons = 0
            fn(*s)
            total += CountingList.comparisons
        return total / len(systems)

    print("       %-26s %8s %10s %14s" % ("system", "DBDAA", "Enhanced", "DBDAA checks"))
    for label, slack, n, spread in (("tight, n=30, staggered", 3, 30, 40),
                                    ("tight, n=100, staggered", 3, 100, 100),
                                    ("tight, n=30, all at 0", 3, 30, 0)):
        systems = good_systems(40, n, slack, spread, 77)
        a = sort_cost(lambda *s: dbd.dbdaa_run(*s), systems)
        b = sort_cost(lambda *s: enh.enhanced_final(*s), systems)
        checks = sum(dbdaa_run(*s)["comparisons"] for s in systems) / len(systems)
        print("       %-26s %8.0f %10.0f %14.0f" % (label, a, b, checks))
        report("Enhanced sorts no more than 5%% above DBDAA (%s)" % label, b <= a * 1.05 + 1)


if __name__ == "__main__":
    test1_paper_numbers()
    test2_check_exact()
    test3_replay()
    test4_verdicts()
    test5_no_hang()
    test6_sorting_cost()
    print("\n" + ("ALL TESTS PASSED" if failures == 0 else "%d TEST(S) FAILED" % failures))
    sys.exit(1 if failures else 0)