# enhanced.py - DBDAA + two modifications (our test implementation)
#   Modification 1: adaptive safety check (switch to a plain check when the system is tight)
#   Modification 2: gated aging (a process that keeps being overtaken by newer ones may go first,
#                   but only if it can run now)
#   Modification 3: idle retry (when nothing is ready to run, retry the parked processes at once
#                   instead of waiting for the end of the 30-unit cycle) - enhanced_final_idle()
# Everything else (cycle m, arrival handling) is the same as dbdaa.py,
# so differences in the results come only from these modifications.
from data import DATASETS, TOTAL_RESOURCES, CYCLE_M
from dbdaa import safety_check as paper_check, show


def plain_check(need_i, available):
    """Plain check: compare each resource, stop at the first one that is not enough.
    Costs at most d comparisons."""
    comparisons = 0
    for j in range(len(available)):
        comparisons += 1
        if need_i[j] > available[j]:
            return False, comparisons
    return True, comparisons


class AdaptiveChecker:
    """
    Modification 1.
    PAPER mode : use DBDAA's check (quick test + marking rounds).
    PLAIN mode : use the plain check.
    Switch PAPER -> PLAIN when the paper's check cost MORE than d comparisons
                 for 'streak_limit' checks in a row (the system is tight).
    Switch PLAIN -> PAPER when a probe (the quick test, 1 comparison) passes.
                 A probe is done on every 'probe_every'-th check in PLAIN mode.
    """

    def __init__(self, streak_limit=2, probe_every=4):
        self.streak_limit = streak_limit
        self.probe_every = probe_every
        self.mode = "paper"
        self.streak = 0
        self.since_probe = 0

    def check(self, need_i, available):
        d = len(available)

        if self.mode == "paper":
            ok, comps = paper_check(need_i, available)
            if comps > d:
                self.streak += 1
            else:
                self.streak = 0
            if self.streak >= self.streak_limit:
                self.mode = "plain"
                self.since_probe = 0
            return ok, comps

        # PLAIN mode
        self.since_probe += 1
        if self.since_probe >= self.probe_every:
            self.since_probe = 0
            if max(need_i) <= min(available):        # probe = the quick test (1 comparison)
                self.mode = "paper"
                self.streak = 0
                return True, 1
            ok, comps = plain_check(need_i, available)
            return ok, comps + 1                      # +1 for the probe
        return plain_check(need_i, available)


def enhanced_run(total, maximum, allocation, burst, arrival,
                 m=CYCLE_M, wait_for_cycle=True, adaptive=True,
                 alpha=0.0, gate_wait=None, probe_gap=5, overtake_limit=None):
    """
    Same simulation as dbdaa_run, with:
      adaptive  : True -> Modification 1 (adaptive check), False -> paper's check
      overtake_limit : Modification 2 (gated aging, final version). None = off.
                  A process is 'overtaken' each time a process that arrived LATER starts
                  running before it. When a waiting process has been overtaken at least
                  overtake_limit times, it is tried FIRST, but only if it passes the
                  1-comparison quick test right now (so it never fails and gets parked).
                  After a failed try, wait 'probe_gap' decisions before trying again, and
                  double that wait after every further failed try (back-off).
      gate_wait : (first version of the gate, kept for comparison in the report)
                  tries the process that has waited longest once it has waited gate_wait
                  time units. Fixed 'probe_gap', no back-off. None = off.
      alpha     : (first, naive version of aging, kept only for comparison in the report)
                  queue key = Max_Need - alpha * (time waited). alpha = 0 means off.
    """
    n = len(maximum)
    d = len(total)

    checker = AdaptiveChecker()
    available = total[:]
    need = [None] * n
    pending = sorted(range(n), key=lambda i: (arrival[i], i))
    ready_queue = []
    max_need = [0] * n

    safe_sequence = []
    primary_unsafe = []
    unsafe_sequence = []
    stuck = []

    timeline = []
    episodes = []
    first_start = [None] * n
    finish_time = [None] * n
    retries = [0] * n

    overtaken = [0] * n      # how many times a later-arriving process ran before process i
    gap_now = probe_gap      # current waiting time between aging tries (grows with back-off)
    queue_dirty = False      # True when the ready queue must be sorted again
    decisions = 0            # how many processes have been picked so far
    next_probe = 0           # earliest decision at which the next aging try is allowed
    clock = 0
    timer = clock + m
    total_comparisons = 0

    ep = {"start": 0, "safe": [], "primary": [], "comps": 0}
    progress = True

    def key(i):
        return max_need[i] - alpha * (clock - arrival[i])

    def admit_arrivals():
        nonlocal progress, queue_dirty
        while pending and arrival[pending[0]] <= clock:
            i = pending.pop(0)
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
            queue_dirty = True

    def end_episode(end_time, retry=True):
        nonlocal timer, ep, queue_dirty
        if ep["safe"] or ep["primary"]:
            ep["end"] = end_time
            episodes.append(ep)
        if retry and primary_unsafe:
            for i in primary_unsafe:
                ready_queue.append(i - 1)
            primary_unsafe.clear()
            queue_dirty = True
        timer = clock + m
        ep = {"start": clock, "safe": [], "primary": [], "comps": 0}

    while True:
        admit_arrivals()

        if ready_queue:
            if queue_dirty or alpha != 0:           # sort only when the queue changed
                ready_queue.sort(key=key)           # stable sort; alpha = 0 -> Max_Need order
                queue_dirty = False

            # ---- Modification 2: gated aging ----
            probe_cost = 0
            picked = None
            use_gate = (overtake_limit is not None) or (gate_wait is not None)
            if use_gate and len(ready_queue) > 1 and decisions >= next_probe:
                if overtake_limit is not None:
                    cand = max(ready_queue, key=lambda x: (overtaken[x], -arrival[x], -x))
                    trigger = cand != ready_queue[0] and overtaken[cand] >= overtake_limit
                else:
                    cand = min(ready_queue, key=lambda x: (arrival[x], x))
                    trigger = cand != ready_queue[0] and clock - arrival[cand] >= gate_wait
                if trigger:
                    probe_cost = 1                   # the quick test costs 1 comparison
                    if max(need[cand]) <= min(available):
                        picked = cand                # it can run now -> let it go first
                        gap_now = probe_gap
                    else:
                        next_probe = decisions + gap_now
                        if overtake_limit is not None:
                            gap_now = min(gap_now * 2, 160)    # back-off
            decisions += 1

            if picked is not None:
                ready_queue.remove(picked)
                i = picked
                ok, comps = True, 0
            else:
                i = ready_queue.pop(0)
                if adaptive:
                    ok, comps = checker.check(need[i], available)
                else:
                    ok, comps = paper_check(need[i], available)
            comps += probe_cost

            total_comparisons += comps
            ep["comps"] += comps
            if ok:
                if first_start[i] is None:
                    first_start[i] = clock
                if overtake_limit is not None:
                    for q in ready_queue:
                        if arrival[q] < arrival[i]:
                            overtaken[q] += 1
                timeline.append((i + 1, clock, clock + burst[i]))
                clock += burst[i]
                finish_time[i] = clock
                for j in range(d):
                    available[j] += allocation[i][j]
                safe_sequence.append(i + 1)
                ep["safe"].append(i + 1)
                progress = True
            else:
                retries[i] += 1
                primary_unsafe.append(i + 1)
                ep["primary"].append(i + 1)
            if clock >= timer:
                end_episode(clock)
            continue

        if primary_unsafe:
            retry_time = timer if wait_for_cycle else clock
            if retry_time < clock:
                retry_time = clock
            if pending and arrival[pending[0]] <= retry_time:
                clock = max(clock, arrival[pending[0]])
                continue
            # retrying at once is pointless if nothing changed since the last retry:
            # stay idle until the next arrival instead (prevents an endless loop)
            if not wait_for_cycle and not progress and pending:
                clock = max(clock, arrival[pending[0]])
                continue
            if not progress and not pending:
                stuck = primary_unsafe[:]
                primary_unsafe.clear()
                end_episode(clock, retry=False)
                break
            progress = False
            episode_end = clock
            clock = retry_time
            end_episode(episode_end)
            continue

        if pending:
            clock = max(clock, arrival[pending[0]])
            continue

        break

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


def enhanced_final(total, maximum, allocation, burst, arrival):
    """Modifications 1 + 2: adaptive check + gated aging.
    Parked processes still wait for the 30-unit cycle, as in the paper's text."""
    return enhanced_run(total, maximum, allocation, burst, arrival,
                        adaptive=True, overtake_limit=5, probe_gap=5)


def enhanced_final_idle(total, maximum, allocation, burst, arrival):
    """Modifications 1 + 2 + 3.
    Modification 3 (idle retry): when the ready queue is empty and the processor would sit
    idle, the parked (Primary Unsafe) processes are retried at once instead of waiting
    for the cycle to end. While the processor is idle nothing can be released, so waiting
    longer could never help."""
    return enhanced_run(total, maximum, allocation, burst, arrival,
                        adaptive=True, overtake_limit=5, probe_gap=5,
                        wait_for_cycle=False)


if __name__ == "__main__":
    for name, (maximum, allocation, bt) in DATASETS.items():
        arrival = [0] * len(maximum)
        res = enhanced_final(TOTAL_RESOURCES, maximum, allocation, bt, arrival)
        show(res, name + "  [enhanced final]")
    for name, (maximum, allocation, bt) in DATASETS.items():
        arrival = [0] * len(maximum)
        res = enhanced_final_idle(TOTAL_RESOURCES, maximum, allocation, bt, arrival)
        show(res, name + "  [enhanced final + idle retry]")