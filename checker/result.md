# Configuration axes
- **Zipf** (0.9/0.7/0.5): contention level (higher = more skewed access)
- **Inter/Intra**: inter-region RTT regime (inter: 60–130ms, intra: 10–12ms)
- **Global/Local**: shard replica placement (globally distributed across regions vs co-located in same region)

---

# Analysis Results: 0.9 Inter-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-18-10-38-03`

```
Config: 2026-03-18-10-38-08
Parsed: 826085 RW, 1399608 RO
Tarjan + classify: found 277 SCCs
Johnson's: 998 cycles, 823 unique skip pairs
SCC sizes: min=3, max=26, median=6, mean=7.5

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            826085 RW + 1399608 RO
C1 (Skip): skip pairs                               473,607  396,342      783
C2 (Anti-dep): valid anti-dep pairs                 406,611  347,971      783
C3 (Window): positive vulnerability window          189,197  175,472      783
    (negative window)                               217,414          (40 in cycle)
C4 (In Cycle): C3 pairs in >= 1 cycle                   783      777      783

  Total anomaly cycles (Johnson's): 998

  Reduction rates:
    C2->C3: x0.465 (53.5% negative window)
    C3->C4: x0.0041 (0.41% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=189197, min=1, max=147916, mean=30687, median=24625
    p10 = 4786
    p25 = 12100
    p50 = 24625
    p75 = 44294
    p90 = 62293
    p99 = 113037
  Positive window (C4 anomaly pairs): n=783, min=612, max=142365, mean=86898, median=101005
    p10 = 21844
    p25 = 51085
    p50 = 101005
    p75 = 117772
    p90 = 126891
    p99 = 140107
  Negative window (abs value): n=217414, min=0, max=3246612, mean=85373, median=70331
    p10 = 8807
    p25 = 34017
    p50 = 70331
    p75 = 104793
    p90 = 155458
    p99 = 485630

======================================================================
CYCLE ANALYSIS (Johnson's algorithm, 998 cycles)
======================================================================

  Cycle lengths: min=3, max=15, median=6

  Theorem C3: every cycle has >= 1 skip pair
    Cycles with skip pair:     998
    Cycles without skip pair:  0  (should be 0)

  Theorem C3: >= 1 positive-window skip pair per cycle
    All positive window:       861
    Mixed (pos + neg):         137  (neg pairs coexist, theorem allows)
    All negative window:       0  (should be 0)

  Window Containment: X.resp in (W.ct, R.invoc-2e)
    X found via RT chain:      998
    Has X in window:           998
    No X in window:            0  (should be 0)
    X position (0=W.ct, 1=R.invoc-2e): min=0.363, median=0.896, max=1.000

  Anomaly type distribution (per cycle, 998 classified):
    Type 1 (non-conflicting RW->RO): 885 (88.7%)
    Type 2 (RO->RO): 113 (11.3%)
```

---

# Analysis Results: 0.9 Inter-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-11-46-41`

```
Config: 2026-03-21-11-46-46
Parsed: 974162 RW, 1588922 RO
Tarjan + classify: found 184 SCCs
Johnson's: 510 cycles, 315 unique skip pairs
SCC sizes: min=3, max=17, median=5, mean=6.4

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            974162 RW + 1588922 RO
C1 (Skip): skip pairs                               195,758  182,446      301
C2 (Anti-dep): valid anti-dep pairs                 151,907  143,740      301
C3 (Window): positive vulnerability window           16,064   15,940      301
    (negative window)                               135,843          (14 in cycle)
C4 (In Cycle): C3 pairs in >= 1 cycle                   301      301      301

  Total anomaly cycles (Johnson's): 510

  Reduction rates:
    C2->C3: x0.106 (89.4% negative window)
    C3->C4: x0.0187 (1.87% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=16064, min=1, max=57348, mean=12096, median=7815
    p10 = 969
    p25 = 2410
    p50 = 7815
    p75 = 19711
    p90 = 30674
    p99 = 39871
  Positive window (C4 anomaly pairs): n=301, min=10533, max=48818, mean=28834, median=30359
    p10 = 17106
    p25 = 23082
    p50 = 30359
    p75 = 34676
    p90 = 37102
    p99 = 41097
  Negative window (abs value): n=135843, min=0, max=2072020, mean=58112, median=37650
    p10 = 10903
    p25 = 22406
    p50 = 37650
    p75 = 67975
    p90 = 134164
    p99 = 303717

======================================================================
CYCLE ANALYSIS (Johnson's algorithm, 510 cycles)
======================================================================

  Cycle lengths: min=3, max=12, median=5

  Theorem C3: every cycle has >= 1 skip pair
    Cycles with skip pair:     510
    Cycles without skip pair:  0  (should be 0)

  Theorem C3: >= 1 positive-window skip pair per cycle
    All positive window:       491
    Mixed (pos + neg):         19  (neg pairs coexist, theorem allows)
    All negative window:       0  (should be 0)

  Window Containment: X.resp in (W.ct, R.invoc-2e)
    X found via RT chain:      510
    Has X in window:           510
    No X in window:            0  (should be 0)
    X position (0=W.ct, 1=R.invoc-2e): min=0.165, median=0.704, max=0.999

  Anomaly type distribution (per cycle, 510 classified):
    Type 1 (non-conflicting RW->RO): 495 (97.1%)
    Type 2 (RO->RO): 15 (2.9%)
```

---

# Analysis Results: 0.9 Intra-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-15-18-11`

```
Config: 2026-03-21-15-18-15
Parsed: 1549357 RW, 2059573 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            1549357 RW + 2059573 RO
C1 (Skip): skip pairs                               403,498  364,693        0
C2 (Anti-dep): valid anti-dep pairs                 313,355  289,373        0
C3 (Window): positive vulnerability window           29,461   29,214        0
    (negative window)                               283,894
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

  Reduction rates:
    C2->C3: x0.094 (90.6% negative window)
    C3->C4: x0.0000 (0.00% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=29461, min=1, max=9539, mean=1626, median=1348
    p10 = 244
    p25 = 626
    p50 = 1348
    p75 = 2292
    p90 = 3354
    p99 = 5797
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=283894, min=0, max=1931229, mean=12632, median=11522
    p10 = 1999
    p25 = 4213
    p50 = 11522
    p75 = 17600
    p90 = 22022
    p99 = 47980
```

---

# Analysis Results: 0.9 Intra-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-12-11-26`

```
Config: 2026-03-21-12-11-31
Parsed: 1808900 RW, 2317022 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            1808900 RW + 2317022 RO
C1 (Skip): skip pairs                                27,682   27,480        0
C2 (Anti-dep): valid anti-dep pairs                  19,692   19,588        0
C3 (Window): positive vulnerability window                0        0        0
    (negative window)                                19,692
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): (empty)
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=19692, min=1309, max=557085, mean=10996, median=9484
    p10 = 7080
    p25 = 8152
    p50 = 9484
    p75 = 11408
    p90 = 15333
    p99 = 30764
```

---

# Analysis Results: 0.7 Inter-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-14-04-43`

```
Config: 2026-03-21-14-04-48
Parsed: 1686452 RW, 1742898 RO
Tarjan + classify: found 2 SCCs
Johnson's: 2 cycles, 3 unique skip pairs
SCC sizes: min=11, max=12, median=12, mean=11.5

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            1686452 RW + 1742898 RO
C1 (Skip): skip pairs                                81,568   79,410        3
C2 (Anti-dep): valid anti-dep pairs                  73,640   71,850        3
C3 (Window): positive vulnerability window           29,390   29,057        3
    (negative window)                                44,250
C4 (In Cycle): C3 pairs in >= 1 cycle                     3        3        3

  Total anomaly cycles (Johnson's): 2

  Reduction rates:
    C2->C3: x0.399 (60.1% negative window)
    C3->C4: x0.0001 (0.01% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=29390, min=2, max=141873, mean=28961, median=23886
    p10 = 4723
    p25 = 11855
    p50 = 23886
    p75 = 42034
    p90 = 58492
    p99 = 101298
  Positive window (C4 anomaly pairs): n=3, min=17788, max=140884, mean=91413, median=115568
    p10 = 17788
    p25 = 17788
    p50 = 115568
    p75 = 140884
    p90 = 140884
    p99 = 140884
  Negative window (abs value): n=44250, min=1, max=11731660, mean=75817, median=69215
    p10 = 11805
    p25 = 36604
    p50 = 69215
    p75 = 98374
    p90 = 127627
    p99 = 255410

======================================================================
CYCLE ANALYSIS (Johnson's algorithm, 2 cycles)
======================================================================

  Cycle lengths: min=11, max=12, median=12

  Theorem C3: every cycle has >= 1 skip pair
    Cycles with skip pair:     2
    Cycles without skip pair:  0  (should be 0)

  Theorem C3: >= 1 positive-window skip pair per cycle
    All positive window:       2
    Mixed (pos + neg):         0  (neg pairs coexist, theorem allows)
    All negative window:       0  (should be 0)

  Window Containment: X.resp in (W.ct, R.invoc-2e)
    X found via RT chain:      2
    Has X in window:           2
    No X in window:            0  (should be 0)
    X position (0=W.ct, 1=R.invoc-2e): min=0.682, median=0.694, max=0.694

  Anomaly type distribution (per cycle, 2 classified):
    Type 1 (non-conflicting RW->RO): 2 (100.0%)
```

---

# Analysis Results: 0.7 Inter-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-14-20-24`

```
Config: 2026-03-21-14-20-28
Parsed: 2240147 RW, 2308011 RO
Tarjan + classify: found 3 SCCs
Johnson's: 4 cycles, 4 unique skip pairs
SCC sizes: min=3, max=6, median=4, mean=4.3

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            2240147 RW + 2308011 RO
C1 (Skip): skip pairs                                35,598   35,232        4
C2 (Anti-dep): valid anti-dep pairs                  30,847   30,572        4
C3 (Window): positive vulnerability window            2,431    2,428        4
    (negative window)                                28,416
C4 (In Cycle): C3 pairs in >= 1 cycle                     4        4        4

  Total anomaly cycles (Johnson's): 4

  Reduction rates:
    C2->C3: x0.079 (92.1% negative window)
    C3->C4: x0.0016 (0.16% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=2431, min=7, max=53094, mean=11706, median=7143
    p10 = 917
    p25 = 2248
    p50 = 7143
    p75 = 18881
    p90 = 30210
    p99 = 45966
  Positive window (C4 anomaly pairs): n=4, min=13980, max=33397, mean=23132, median=26687
    p10 = 13980
    p25 = 18465
    p50 = 26687
    p75 = 33397
    p90 = 33397
    p99 = 33397
  Negative window (abs value): n=28416, min=1, max=1588544, mean=44741, median=36422
    p10 = 13450
    p25 = 23705
    p50 = 36422
    p75 = 60030
    p90 = 81760
    p99 = 169113

======================================================================
CYCLE ANALYSIS (Johnson's algorithm, 4 cycles)
======================================================================

  Cycle lengths: min=3, max=5, median=4

  Theorem C3: every cycle has >= 1 skip pair
    Cycles with skip pair:     4
    Cycles without skip pair:  0  (should be 0)

  Theorem C3: >= 1 positive-window skip pair per cycle
    All positive window:       4
    Mixed (pos + neg):         0  (neg pairs coexist, theorem allows)
    All negative window:       0  (should be 0)

  Window Containment: X.resp in (W.ct, R.invoc-2e)
    X found via RT chain:      4
    Has X in window:           4
    No X in window:            0  (should be 0)
    X position (0=W.ct, 1=R.invoc-2e): min=0.361, median=0.592, max=0.837

  Anomaly type distribution (per cycle, 4 classified):
    Type 1 (non-conflicting RW->RO): 4 (100.0%)
```

---

# Analysis Results: 0.7 Intra-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-14-37-42`

```
Config: 2026-03-21-14-37-46
Parsed: 3118199 RW, 3146464 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            3118199 RW + 3146464 RO
C1 (Skip): skip pairs                                56,470   55,927        0
C2 (Anti-dep): valid anti-dep pairs                  49,630   49,195        0
C3 (Window): positive vulnerability window            3,196    3,194        0
    (negative window)                                46,434
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

  Reduction rates:
    C2->C3: x0.064 (93.6% negative window)
    C3->C4: x0.0000 (0.00% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=3196, min=1, max=7087, mean=1370, median=1132
    p10 = 205
    p25 = 539
    p50 = 1132
    p75 = 1936
    p90 = 2863
    p99 = 4838
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=46434, min=0, max=1503197, mean=12134, median=12060
    p10 = 2492
    p25 = 5461
    p50 = 12060
    p75 = 17191
    p90 = 20400
    p99 = 26733
```

---

# Analysis Results: 0.7 Intra-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-21-14-56-30`

```
Config: 2026-03-21-14-56-34
Parsed: 3927157 RW, 3953305 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            3927157 RW + 3953305 RO
C1 (Skip): skip pairs                                 3,178    3,178        0
C2 (Anti-dep): valid anti-dep pairs                   2,790    2,790        0
C3 (Window): positive vulnerability window                0        0        0
    (negative window)                                 2,790
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): (empty)
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=2790, min=2631, max=867985, mean=9831, median=9197
    p10 = 7468
    p25 = 8251
    p50 = 9197
    p75 = 10160
    p90 = 11351
    p99 = 18872
```

---

# Analysis Results: 0.5 Inter-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-22-14-37-22`

```
Config: 2026-03-22-14-37-27
Parsed: 2278626 RW, 2280969 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            2278626 RW + 2280969 RO
C1 (Skip): skip pairs                                 7,183    7,168        0
C2 (Anti-dep): valid anti-dep pairs                   5,610    5,603        0
C3 (Window): positive vulnerability window            2,049    2,048        0
    (negative window)                                 3,561
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

  Reduction rates:
    C2->C3: x0.365 (63.5% negative window)
    C3->C4: x0.0000 (0.00% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=2049, min=29, max=123868, mean=28091, median=23828
    p10 = 4614
    p25 = 11818
    p50 = 23828
    p75 = 41193
    p90 = 56072
    p99 = 88236
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=3561, min=37, max=735786, mean=72375, median=71478
    p10 = 13501
    p25 = 37598
    p50 = 71478
    p75 = 100164
    p90 = 129574
    p99 = 169089
```

---

# Analysis Results: 0.5 Inter-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-22-14-51-13`

```
Config: 2026-03-22-14-51-17
Parsed: 2832851 RW, 2835945 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            2832851 RW + 2835945 RO
C1 (Skip): skip pairs                                 2,299    2,294        0
C2 (Anti-dep): valid anti-dep pairs                   1,844    1,843        0
C3 (Window): positive vulnerability window              124      124        0
    (negative window)                                 1,720
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

  Reduction rates:
    C2->C3: x0.067 (93.3% negative window)
    C3->C4: x0.0000 (0.00% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=124, min=381, max=45385, mean=9056, median=5563
    p10 = 951
    p25 = 1977
    p50 = 5563
    p75 = 15226
    p90 = 19352
    p99 = 43287
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=1720, min=1, max=1929148, mean=45298, median=37508
    p10 = 15753
    p25 = 26421
    p50 = 37508
    p75 = 61593
    p90 = 80784
    p99 = 100478
```

---

# Analysis Results: 0.5 Intra-Global (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-22-15-06-03`

```
Config: 2026-03-22-15-06-07
Parsed: 4022417 RW, 4022657 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            4022417 RW + 4022657 RO
C1 (Skip): skip pairs                                 2,862    2,861        0
C2 (Anti-dep): valid anti-dep pairs                   2,408    2,407        0
C3 (Window): positive vulnerability window              117      117        0
    (negative window)                                 2,291
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

  Reduction rates:
    C2->C3: x0.049 (95.1% negative window)
    C3->C4: x0.0000 (0.00% pass reachability)

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): n=117, min=16, max=4084, mean=1267, median=1093
    p10 = 228
    p25 = 459
    p50 = 1093
    p75 = 1939
    p90 = 2596
    p99 = 3835
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=2291, min=16, max=618817, mean=13449, median=13705
    p10 = 3064
    p25 = 7181
    p50 = 13705
    p75 = 18625
    p90 = 21720
    p99 = 29003
```

---

# Analysis Results: 0.5 Intra-Local (TT=4ms)

Dataset: `/root/sejongkim/chronos/experiments/results2/tt-4ms/2026-03-22-15-22-19`

```
Config: 2026-03-22-15-22-23
Parsed: 4478334 RW, 4477244 RO
Tarjan + classify: found 0 SCCs
Johnson's: 0 cycles, 0 unique skip pairs

======================================================================
FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)
======================================================================

Stage                                                 Pairs      ROs    In C4
----------------------------------------------------------------------------
Input                                            4478334 RW + 4477244 RO
C1 (Skip): skip pairs                                   147      147        0
C2 (Anti-dep): valid anti-dep pairs                     122      122        0
C3 (Window): positive vulnerability window                0        0        0
    (negative window)                                   122
C4 (In Cycle): C3 pairs in >= 1 cycle                     0        0        0

  Total anomaly cycles (Johnson's): 0

======================================================================
VULNERABILITY WINDOW DISTRIBUTION (us)
======================================================================
  Positive window (all C3 pairs): (empty)
  Positive window (C4 anomaly pairs): (empty)
  Negative window (abs value): n=122, min=6367, max=19872, mean=9747, median=9462
    p10 = 7902
    p25 = 8580
    p50 = 9462
    p75 = 10443
    p90 = 11357
    p99 = 18397
```
