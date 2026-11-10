# dbdaa.py - DBDAA (Dynamic Banker's Deadlock Avoidance Algorithm), complete version
# Step 2 part : safety_check()
# Step 3 part : dbdaa_run() = arrivals + sorted ready queue + timer cycle + retries
from data import DATASETS, TOTAL_RESOURCES, CYCLE_M


def safety_check(need_i, available):
    """
    DBDAA optimized safety check for ONE process (paper Algorithm 1, steps 14-41).
    Returns (is_safe, comparisons).

    Compare Max_Need (largest unmarked need) with Min_A (smallest unmarked
    available). If Max_Need <= Min_A the process is safe in 1 comparison.
    Otherwise check the two 'problem' resources (L1, L2), mark them, and repeat
    for at most floor(d/2) rounds.
    """
    d = len(available)
    marked = [False] * d
    comparisons = 0
    k = 1

    while k <= d // 2:
        l1 = -1
        l2 = -1
        for j in range(d):
            if not marked[j]:
                if l1 == -1 or need_i[j] > need_i[l1]:
                    l1 = j
                if l2 == -1 or available[j] < available[l2]:
                    l2 = j

        comparisons += 1
        if need_i[l1] <= available[l2]:
            return True, comparisons

        comparisons += 1
        if need_i[l1] > available[l1]:
            return False, comparisons
        comparisons += 1
        if need_i[l2] > available[l2]:
            return False, comparisons

        marked[l1] = True
        marked[l2] = True
        k += 1

    for j in range(d):
        if not marked[j]:
            comparisons += 1
            if need_i[j] > available[j]:
                return False, comparisons
    return True, comparisons


def dbdaa_run(total, maximum, allocation, burst, arrival, m=CYCLE_M, wait_for_cycle=True):
    """
    Full DBDAA simulation on a single processor.

    total, maximum, allocation, burst, arrival : input data (process i = row i)
    m              : cycle length (paper uses 30)
    wait_for_cycle : True  -> Primary Unsafe processes go back to the ready queue only
                              when the cycle (timer) ends   (paper text / your flowchart)
                     False -> they go back as soon as the ready queue becomes empty

    Returns a dict with sequences, timeline, episodes, comparisons and per-process info.
    """
    n = len(maximum)
    d = len(total)

    available = total[:]
    need = [None] * n
    pending = sorted(range(n), key=lambda i: (arrival[i], i))   # not yet arrived
    ready_queue = []            # process indexes, kept sorted by Max_Need
    max_need = [0] * n

    safe_sequence = []
    primary_unsafe = []         # currently waiting for retry
    unsafe_sequence = []        # can never be satisfied (Maximum > Total)
    stuck = []                  # (our addition) no progress possible, stop retrying

    timeline = []               # (process number, start, end)
    episodes = []               # one record per cycle
    first_start = [None] * n
    finish_time = [None] * n
    retries = [0] * n

    clock = 0
    timer = clock + m
    total_comparisons = 0

    # data collected for the current episode
    ep = {"start": 0, "safe": [], "primary": [], "comps": 0}
    progress = True             # did anything change since the last retry?

    def admit_arrivals():
        """Paper steps 3-5: new processes join the system instantly."""
        nonlocal progress
        admitted = False
        while pending and arrival[pending[0]] <= clock:
            i = pending.pop(0)
            admitted = True
            progress = True
            too_big = False
            for j in range(d):
                if maximum[i][j] > total[j]:
                    too_big = True
            if too_big:
                unsafe_sequence.append(i + 1)
                continue
            need[i] = [maximum[i][j] - allocation[i][j] for j in range(d)]
            for j in range(d):
                available[j] -= allocation[i][j]
                if available[j] < 0:
                    raise ValueError("Invalid input: allocations exceed total resources")
            max_need[i] = max(need[i])
            ready_queue.append(i)
        if admitted:
            ready_queue.sort(key=lambda x: max_need[x])      # stable sort

    def end_episode(end_time, retry=True):
        """Paper step 8: return the sequences, move Primary Unsafe back to the queue."""
        nonlocal timer, ep, progress
        if ep["safe"] or ep["primary"]:
            ep["end"] = end_time
            episodes.append(ep)
        if retry and primary_unsafe:
            for i in primary_unsafe:
                ready_queue.append(i - 1)
            primary_unsafe.clear()
            ready_queue.sort(key=lambda x: max_need[x])
        timer = clock + m
        ep = {"start": clock, "safe": [], "primary": [], "comps": 0}

    while True:
        admit_arrivals()

        if ready_queue:
            i = ready_queue.pop(0)
            ok, comps = safety_check(need[i], available)
            total_comparisons += comps
            ep["comps"] += comps
            if ok:
                if first_start[i] is None:
                    first_start[i] = clock
                timeline.append((i + 1, clock, clock + burst[i]))
                clock += burst[i]
                finish_time[i] = clock
                for j in range(d):
                    available[j] += allocation[i][j]        # release resources
                safe_sequence.append(i + 1)
                ep["safe"].append(i + 1)
                progress = True
            else:
                retries[i] += 1
                primary_unsafe.append(i + 1)
                ep["primary"].append(i + 1)
            # timer check (paper step 8)
            if clock >= timer:
                end_episode(clock)
            continue

        # ---- ready queue is empty ----
        if primary_unsafe:
            retry_time = timer if wait_for_cycle else clock
            if retry_time < clock:
                retry_time = clock
            # a new process may arrive before the retry happens
            if pending and arrival[pending[0]] <= retry_time:
                clock = max(clock, arrival[pending[0]])
                continue
            # retrying at once is pointless if nothing changed since the last retry:
            # stay idle until the next arrival instead (prevents an endless loop)
            if not wait_for_cycle and not progress and pending:
                clock = max(clock, arrival[pending[0]])
                continue
            if not progress and not pending:
                stuck = primary_unsafe[:]       # nothing changed -> retrying is useless
                primary_unsafe.clear()
                end_episode(clock, retry=False)
                break
            progress = False
            episode_end = clock
            clock = retry_time
            end_episode(episode_end)
            continue

        if pending:
            clock = max(clock, arrival[pending[0]])     # processor idle until next arrival
            continue

        break                                            # everything is done

    end_episode(clock, retry=False)

    return {
        "safe_sequence": safe_sequence,
        "unsafe_sequence": unsafe_sequence,
        "stuck": stuck,
        "timeline": timeline,
        "episodes": episodes,
        "comparisons": total_comparisons,
        "first_start": first_start,
        "finish_time": finish_time,
        "retries": retries,
        "end_time": clock,
    }


def show(result, title):
    print(title)
    for e, ep in enumerate(result["episodes"], 1):
        print("  Episode", e, "(time", str(ep["start"]) + "-" + str(ep["end"]) + ")")
        print("    Safe_Sequence          :", ["P" + str(p) for p in ep["safe"]])
        print("    Primary_Unsafe_Sequence:", ["P" + str(p) for p in ep["primary"]])
        print("    Comparisons            :", ep["comps"])
    print("  Unsafe_Sequence (Max > Total):", ["P" + str(p) for p in result["unsafe_sequence"]])
    print("  Stuck (no progress possible)  :", ["P" + str(p) for p in result["stuck"]])
    print("  Timeline:", " ".join("P%d[%d-%d]" % t for t in result["timeline"]))
    print("  Total comparisons:", result["comparisons"], " | finished at time", result["end_time"])
    print()


if __name__ == "__main__":
    # 1) the paper's three datasets (all arrive at time 0)
    for name, (maximum, allocation, bt) in DATASETS.items():
        arrival = [0] * len(maximum)
        res = dbdaa_run(TOTAL_RESOURCES, maximum, allocation, bt, arrival)
        show(res, name)

    # 2) demo of dynamic arrival: Table 3 data with staggered arrival times
    maximum, allocation, bt = DATASETS["Table 3 (average)"]
    arrival = [0, 0, 0, 0, 0, 3, 3, 6, 6, 9]
    res = dbdaa_run(TOTAL_RESOURCES, maximum, allocation, bt, arrival)
    show(res, "Demo: Table 3 with staggered arrival times " + str(arrival))