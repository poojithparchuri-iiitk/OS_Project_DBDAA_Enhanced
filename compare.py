# compare.py - side by side comparison: Traditional Banker's vs DBDAA (paper datasets)
from data import DATASETS, TOTAL_RESOURCES, get_available
from bankers import bankers_safety
from dbdaa import dbdaa_run


def validate_sequence(sequence, available, maximum, allocation):
    """Independent check: is this order really a safe order?
    Each process in turn must satisfy Need <= Work, then releases its allocation."""
    work = available[:]
    d = len(work)
    for p in sequence:
        i = p - 1
        for j in range(d):
            if maximum[i][j] - allocation[i][j] > work[j]:
                return False
        for j in range(d):
            work[j] += allocation[i][j]
    return True


def bankers_times(sequence, burst):
    """Traditional Banker's only gives a safe order. To get time metrics we assume
    the processes are executed in that order, one after another (AT = 0)."""
    start = {}
    finish = {}
    t = 0
    for p in sequence:
        start[p] = t
        t += burst[p - 1]
        finish[p] = t
    return start, finish, t


def average(values):
    return sum(values) / len(values)


if __name__ == "__main__":
    rows = []
    for name, (maximum, allocation, bt) in DATASETS.items():
        n = len(maximum)
        available = get_available(allocation)

        # ---- traditional Banker's ----
        safe, seq, comps = bankers_safety(available, maximum, allocation)
        b_checks = comps // len(available)
        b_start, b_finish, b_end = bankers_times(seq, bt)
        b_wait = average([b_start[p] for p in seq])
        b_turn = average([b_finish[p] for p in seq])
        b_valid = validate_sequence(seq, available, maximum, allocation)

        # ---- DBDAA ----
        res = dbdaa_run(TOTAL_RESOURCES, maximum, allocation, bt, [0] * n)
        d_seq = res["safe_sequence"]
        d_checks = 0
        for ep in res["episodes"]:
            d_checks += len(ep["safe"]) + len(ep["primary"])
        d_first = res["episodes"][0]["comps"]
        d_wait = average(res["first_start"])
        d_turn = average(res["finish_time"])
        d_valid = validate_sequence(d_seq, available, maximum, allocation)
        busy = sum(bt)
        d_idle = res["end_time"] - busy

        print("=" * 66)
        print(name)
        print("=" * 66)
        print("%-34s %-14s %-14s" % ("", "Traditional", "DBDAA"))
        print("%-34s %-14s %-14s" % ("System safe?", "YES" if safe else "NO", "YES"))
        print("%-34s %-14s %-14s" % ("Safe order valid (re-checked)?", b_valid, d_valid))
        print("%-34s %-14d %-14d" % ("Safety checks (process checks)", b_checks, d_checks))
        print("%-34s %-14d %-14d" % ("Comparisons, first pass (paper)", comps, d_first))
        print("%-34s %-14d %-14d" % ("Comparisons, total incl. retries", comps, res["comparisons"]))
        print("%-34s %-14d %-14d" % ("Finish time of all processes", b_end, res["end_time"]))
        print("%-34s %-14d %-14d" % ("Processor idle time", 0, d_idle))
        print("%-34s %-14.1f %-14.1f" % ("Average waiting time", b_wait, d_wait))
        print("%-34s %-14.1f %-14.1f" % ("Average turnaround time", b_turn, d_turn))
        print("Traditional order:", " ".join("P" + str(p) for p in seq))
        print("DBDAA order      :", " ".join("P" + str(p) for p in d_seq))
        print()

        rows.append((name, comps, d_first, res["comparisons"]))

    print("=" * 66)
    print("Summary of comparisons (lower is better)")
    print("=" * 66)
    print("%-20s %-12s %-14s %-14s %-10s" % ("Dataset", "Traditional", "DBDAA 1st pass", "DBDAA total", "Saved (1st)"))
    for name, t, f, tot in rows:
        saved = 100.0 * (t - f) / t
        print("%-20s %-12d %-14d %-14d %.1f%%" % (name, t, f, tot, saved))