# DBDAA: Dynamic Banker's Deadlock Avoidance Algorithm

OS course project: a from-scratch Python reimplementation of DBDAA, validated against the paper,
plus our own modifications and the experiments that compare them.

Paper: Zohora M.F., Farhin F., Kaiser M.S. (2024), "DBDAA: A real-time approach to Dynamic Banker's
Deadlock Avoidance Algorithm with optimized time complexity", PLOS ONE 19(9): e0310807.
https://doi.org/10.1371/journal.pone.0310807

## Files

| File | What it does |
|---|---|
| `data.py` | The paper's three datasets (Tables 2, 3, 4 = Data 1, 2, 3) |
| `bankers.py` | Traditional Banker's safety algorithm |
| `dbdaa.py` | DBDAA (arrivals, sorted queue, optimized safety check, timer cycle, retries) |
| `enhanced.py` | Our version: adaptive safety check, gated aging, optional idle retry |
| `compare.py`, `compare2.py` | Early comparison scripts |
| `final_compare.py` | All final experiments |
| `results.txt` | Output of `final_compare.py` |

## Run

Python 3.8+ and the standard library only.

    python bankers.py
    python dbdaa.py
    python enhanced.py
    python final_compare.py

## Validation

On the paper's data the traditional algorithm needs 85 / 100 / 125 comparisons and DBDAA needs
10 / 36 / 70 in its first round, matching the paper's Table 8. The safe sequences and timelines
match the paper's Tables 5-7 and Figs 3-5.

## Our modifications

1. Adaptive check: switch to a plain check when DBDAA's shortcut keeps failing (tight systems).
2. Gated aging: a long-waiting process may go first, but only if it can run right now.
3. Idle retry: retry parked processes as soon as the processor would be idle, instead of waiting
   for the 30-unit cycle (this is the second reading of the paper's flowchart).

2. Gated aging: a process that has been overtaken at least 5 times by later arrivals may go first,
   but only if it can run right now (1-comparison test, with back-off after failed tries).

## Status and known issues

- The paper does not count sorting. In our measurements DBDAA's sorting costs about as much as its
  safety checks; our version sorts exactly as much as DBDAA (it re-sorts only when the queue changes).
- Our version is better than DBDAA in tight systems, break-even when slightly tight, and slightly
  worse (+3 to +5 comparisons) in loose systems with staggered arrivals.
- Not modelled: processes requesting more resources while running, multiple processors, preemption.
