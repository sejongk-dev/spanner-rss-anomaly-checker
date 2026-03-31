#!/usr/bin/env python3
"""Structural decomposition: Why does high skip rate -> tiny anomaly rate?

Identifies the filter cascade from skip pairs to actual anomaly cycles,
decomposing the necessary conditions for an RSS SS-violation cycle:

  X --(RT)--> skipping RO --(RW anti-dep)--> skipped RW --(dep|RT)*--> X

Key insight: every SS-violation cycle must contain at least one skip pair
(R, W) with positive vulnerability window: W.commit_ts < R.invoc_ts - 2*clock_err
(Theorem C3). This is NOT guaranteed by the skip condition alone
(skip only requires W.commit_ts > R.snapshot_ts).

All cycles are enumerated via Johnson's algorithm on each SCC.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checker import (
    find_experiment, get_committed_transactions, apply_limit,
    DSGChecker,
)


def pstats(label, vals):
    if not vals:
        print("  %s: (empty)" % label)
        return
    vals_s = sorted(vals)
    n = len(vals_s)
    mean = sum(vals_s) / n
    print("  %s: n=%d, min=%d, max=%d, mean=%.0f, median=%d" % (
        label, n, vals_s[0], vals_s[-1], mean, vals_s[n//2]))
    for p in [10, 25, 50, 75, 90, 99]:
        idx = min(int(n * p / 100), n-1)
        print("    p%d = %d" % (p, vals_s[idx]))


def _find_skip_pairs_on_cycle(cycle, tx_by_id, rw_by_id, checker):
    """Identify (RO, skipped_RW) skip pairs on a cycle with valid anti-dep."""
    cycle_set = set(cycle)
    pairs = []
    for node_id in cycle:
        tx = tx_by_id.get(node_id)
        if tx is None or tx.is_rw:
            continue
        ro = tx
        if not hasattr(ro, 'skipped_rws'):
            continue
        for sw_id, _ in ro.skipped_rws:
            if sw_id not in cycle_set:
                continue
            sw = rw_by_id.get(sw_id)
            if sw is None:
                continue
            has_antidep = any(
                checker.next_writer_of.get((k, wid)) == sw_id
                for k, wid in ro.reads
            )
            if has_antidep:
                pairs.append((ro, sw))
    return pairs


def _find_x_by_rt_chain(ro, cycle, idx_of, tx_by_id, clock_err):
    """Find X by walking backward from RO through consecutive RT edges.

    Starting from RO's predecessor on the cycle, follow RT edges backward
    (transitive reduction). Stop when a non-RT edge is found. The node
    at the start of the RT chain is X.

    Returns (X transaction, rt_chain_length) or (None, 0) if RO's
    predecessor is not connected via RT.
    """
    e2 = 2 * clock_err
    n = len(cycle)
    ro_idx = idx_of[ro.id]
    x_idx = ro_idx
    steps = 0
    while steps < n - 1:
        pred_idx = (x_idx - 1) % n
        pred = tx_by_id.get(cycle[pred_idx])
        curr = tx_by_id.get(cycle[x_idx])
        if pred is None or curr is None:
            break
        if pred.resp_ts + e2 < curr.invoc_ts:  # RT edge
            x_idx = pred_idx
            steps += 1
        else:
            break
    if x_idx == ro_idx:
        return None, 0  # no RT edge into RO on this cycle
    return tx_by_id.get(cycle[x_idx]), steps


def run_analysis(config: dict, out_dir: str, clock_err: int,
                 limit: int = 0, run: int = 0) -> None:
    e2 = 2 * clock_err

    # ─── Load Data ───
    t0 = time.time()
    rw_list, ro_list = get_committed_transactions(config, out_dir, run)
    print("Parsed: %d RW, %d RO (%.1fs)" % (len(rw_list), len(ro_list), time.time()-t0))

    if limit > 0:
        rw_list, ro_list = apply_limit(rw_list, ro_list, limit)
        print("After --limit %d: %d RW, %d RO" % (limit, len(rw_list), len(ro_list)))

    # Build checker
    t0 = time.time()
    checker = DSGChecker(rw_list, ro_list, clock_err)
    print("Checker phases 1-2: %.1fs" % (time.time()-t0))

    # Run Tarjan + Johnson's to get all cycles
    t0 = time.time()
    anomalies = checker.find_anomalies()
    print("Tarjan + classify: %.1fs, found %d SCCs" % (time.time()-t0, len(anomalies)))

    rw_by_id = {rw.id: rw for rw in rw_list}
    tx_by_id = {**rw_by_id, **{ro.id: ro for ro in ro_list}}

    # ─── Extract Johnson's cycles and derive anomaly pairs ───
    all_johnson_cycles = []
    for a in anomalies:
        all_johnson_cycles.extend(a.get('all_cycles', []))

    # Derive anomaly pairs from Johnson's cycles (ground truth)
    johnsons_pairs = set()  # (ro_id, sw_id)
    for cycle in all_johnson_cycles:
        for ro, sw in _find_skip_pairs_on_cycle(cycle, tx_by_id, rw_by_id, checker):
            johnsons_pairs.add((ro.id, sw.id))

    print("Johnson's: %d cycles, %d unique skip pairs" % (
        len(all_johnson_cycles), len(johnsons_pairs)))

    # SCC size distribution
    scc_sizes = sorted([a['scc_size'] for a in anomalies])
    if scc_sizes:
        print("SCC sizes: min=%d, max=%d, median=%d, mean=%.1f" % (
            scc_sizes[0], scc_sizes[-1], scc_sizes[len(scc_sizes)//2],
            sum(scc_sizes)/len(scc_sizes)))

    # ═══════════════════════════════════════════
    # FILTER CASCADE (C1-C4)
    # Primary unit: skip pair (RO, skipped_RW)
    # Secondary: unique skipping ROs
    # ═══════════════════════════════════════════
    print("\n" + "="*70)
    print("FILTER CASCADE: C1(Skip) -> C2(Anti-dep) -> C3(Window) -> C4(In Cycle)")
    print("="*70)

    # Input
    total_ros = len(ro_list)
    total_rws = len(rw_list)

    # C1: All skip pairs from logs
    c1_pairs = set()
    for ro in ro_list:
        if hasattr(ro, 'skipped_rws') and ro.skipped_rws:
            for sw_id, _ in ro.skipped_rws:
                c1_pairs.add((ro.id, sw_id))
    c1_ros = len(set(ro_id for ro_id, _ in c1_pairs))

    # C2: Valid anti-dep pairs
    c2_pairs = {}  # (ro_id, sw_id) -> (ro, sw)
    for ro in ro_list:
        if not (hasattr(ro, 'skipped_rws') and ro.skipped_rws):
            continue
        skipped_ids = set(s[0] for s in ro.skipped_rws)
        for key, writer_id in ro.reads:
            next_w = checker.next_writer_of.get((key, writer_id))
            if next_w is not None and next_w in skipped_ids and next_w in rw_by_id:
                if (ro.id, next_w) not in c2_pairs:
                    c2_pairs[(ro.id, next_w)] = (ro, rw_by_id[next_w])
    c2_ros = len(set(ro_id for ro_id, _ in c2_pairs))

    if not c2_pairs:
        print("\nNo valid anti-dep pairs found. Skipping cascade analysis.")
        return

    # C3: Positive vulnerability window
    c3_pos_pairs = {}   # (ro_id, sw_id) -> (ro, sw, window)
    c3_neg_pairs = {}
    for (ro_id, sw_id), (ro, sw) in c2_pairs.items():
        window = (ro.invoc_ts - e2) - sw.commit_ts
        if window > 0:
            c3_pos_pairs[(ro_id, sw_id)] = (ro, sw, window)
        else:
            c3_neg_pairs[(ro_id, sw_id)] = (ro, sw, -window)
    c3_pos_ros = len(set(ro_id for ro_id, _ in c3_pos_pairs))

    # C4: Positive-window pairs that appear in at least 1 Johnson's cycle
    # (C4 ⊂ C3 positive: strict subset chain C1 ⊃ C2 ⊃ C3 ⊃ C4)
    c4_pairs = johnsons_pairs & set(c3_pos_pairs.keys())
    c4_ros = len(set(ro_id for ro_id, _ in c4_pairs))
    # Note: negative-window pairs in cycles are tracked separately in CYCLE ANALYSIS
    c4_neg_in_cycle = len(johnsons_pairs & set(c3_neg_pairs.keys()))

    # Count anomaly pairs at each stage (how many survive to C4)
    c1_anom = len(c1_pairs & c4_pairs)
    c2_anom = len(set(c2_pairs.keys()) & c4_pairs)

    # Print cascade table
    hdr = "%-48s %10s %8s %8s"
    row = "%-48s %10s %8s %8s"
    print("\n" + hdr % ("Stage", "Pairs", "ROs", "In C4"))
    print("-" * 76)
    print(row % ("Input",
                 "%d RW + %d RO" % (total_rws, total_ros), "", ""))
    print(row % ("C1 (Skip): skip pairs",
                 "{:,}".format(len(c1_pairs)),
                 "{:,}".format(c1_ros),
                 str(c1_anom)))
    print(row % ("C2 (Anti-dep): valid anti-dep pairs",
                 "{:,}".format(len(c2_pairs)),
                 "{:,}".format(c2_ros),
                 str(c2_anom)))
    print(row % ("C3 (Window): positive vulnerability window",
                 "{:,}".format(len(c3_pos_pairs)),
                 "{:,}".format(c3_pos_ros),
                 str(len(c4_pairs))))
    print(row % ("    (negative window)",
                 "{:,}".format(len(c3_neg_pairs)),
                 "",
                 "(%d in cycle)" % c4_neg_in_cycle if c4_neg_in_cycle else ""))
    print(row % ("C4 (In Cycle): C3 pairs in >= 1 cycle",
                 "{:,}".format(len(c4_pairs)),
                 "{:,}".format(c4_ros),
                 str(len(c4_pairs))))
    print()
    print("  Total anomaly cycles (Johnson's): %d" % len(all_johnson_cycles))

    # Reduction rates
    if len(c2_pairs) > 0 and len(c3_pos_pairs) > 0:
        print("\n  Reduction rates:")
        print("    C2->C3: x%.3f (%.1f%% negative window)" % (
            len(c3_pos_pairs)/len(c2_pairs),
            100*len(c3_neg_pairs)/len(c2_pairs)))
        print("    C3->C4: x%.4f (%.2f%% pass reachability)" % (
            len(c4_pairs)/max(1, len(c3_pos_pairs)),
            100*len(c4_pairs)/max(1, len(c3_pos_pairs))))

    # ═══════════════════════════════════════════
    # VULNERABILITY WINDOW DISTRIBUTION
    # ═══════════════════════════════════════════
    print("\n" + "="*70)
    print("VULNERABILITY WINDOW DISTRIBUTION (us)")
    print("="*70)

    pos_w = [w for _,_,w in c3_pos_pairs.values()]
    neg_w = [w for _,_,w in c3_neg_pairs.values()]
    anom_w = [w for (rid, sid), (_,_,w) in c3_pos_pairs.items()
              if (rid, sid) in c4_pairs]

    pstats("Positive window (all C3 pairs)", pos_w)
    pstats("Positive window (C4 anomaly pairs)", anom_w)
    pstats("Negative window (abs value)", neg_w)

    # ═══════════════════════════════════════════
    # CYCLE ANALYSIS (Johnson's, per cycle)
    # ═══════════════════════════════════════════
    if all_johnson_cycles:
        print("\n" + "="*70)
        print("CYCLE ANALYSIS (Johnson's algorithm, %d cycles)" % len(all_johnson_cycles))
        print("="*70)

        # Cycle length distribution
        cycle_lengths = [len(c) for c in all_johnson_cycles]
        cl = sorted(cycle_lengths)
        print("\n  Cycle lengths: min=%d, max=%d, median=%d" % (
            cl[0], cl[-1], cl[len(cl)//2]))

        # Per-cycle: theorem validation + type classification
        # X found via RT chain backward walk (transitive reduction)
        cycles_with_skip = 0
        cycles_no_skip = 0
        cycles_has_pos = 0
        cycles_all_neg = 0
        cycles_mixed = 0       # has both positive and negative window pairs
        cycles_has_x_in = 0
        cycles_pos_no_x = 0
        cycles_x_not_found = 0  # no RT edge into RO (non-standard pattern)
        x_positions = []

        # Type classification (per cycle — first X found determines type)
        type_counts = {}  # rt_type -> count

        for cycle in all_johnson_cycles:
            idx_of = {node: i for i, node in enumerate(cycle)}
            skip_pairs = _find_skip_pairs_on_cycle(
                cycle, tx_by_id, rw_by_id, checker)

            if not skip_pairs:
                cycles_no_skip += 1
                continue
            cycles_with_skip += 1

            # For each skip pair: check C3, find X via RT chain, check containment
            has_pos = False
            has_neg = False
            has_x_in = False
            cycle_classified = False

            for ro, sw in skip_pairs:
                window_lower = sw.commit_ts
                window_upper = ro.invoc_ts - e2
                window_size = window_upper - window_lower
                if window_size <= 0:
                    has_neg = True
                    continue
                has_pos = True

                # Find X: walk backward from RO through consecutive RT edges
                x, rt_hops = _find_x_by_rt_chain(
                    ro, cycle, idx_of, tx_by_id, clock_err)

                if x is None:
                    continue  # no RT edge into RO on this cycle

                # Window containment check
                if window_lower < x.resp_ts < window_upper:
                    has_x_in = True
                    x_positions.append(
                        (x.resp_ts - window_lower) / window_size)

                # Type classification (once per cycle, based on first X found)
                if not cycle_classified:
                    if x.is_rw:
                        conflict = (x.write_keys_set & set(k for k, _ in ro.reads)
                                    if hasattr(x, 'write_keys_set') else set())
                        if conflict:
                            rt_type = 'Type 1c (conflicting RW->RO)'
                        else:
                            rt_type = 'Type 1 (non-conflicting RW->RO)'
                    else:
                        rt_type = 'Type 2 (RO->RO)'
                    type_counts[rt_type] = type_counts.get(rt_type, 0) + 1
                    cycle_classified = True

            if has_pos:
                cycles_has_pos += 1
                if has_neg:
                    cycles_mixed += 1
                if has_x_in:
                    cycles_has_x_in += 1
                elif not cycle_classified:
                    cycles_x_not_found += 1
                else:
                    cycles_pos_no_x += 1
            else:
                cycles_all_neg += 1

        # Theorem validation
        print("\n  Theorem C3: every cycle has >= 1 skip pair")
        print("    Cycles with skip pair:     %d" % cycles_with_skip)
        print("    Cycles without skip pair:  %d  (should be 0)" % cycles_no_skip)

        print("\n  Theorem C3: >= 1 positive-window skip pair per cycle")
        print("    All positive window:       %d" % (cycles_has_pos - cycles_mixed))
        print("    Mixed (pos + neg):         %d  (neg pairs coexist, theorem allows)" % cycles_mixed)
        print("    All negative window:       %d  (should be 0)" % cycles_all_neg)

        print("\n  Window Containment: X.resp in (W.ct, R.invoc-2e)")
        print("    X found via RT chain:      %d" % (cycles_has_x_in + cycles_pos_no_x))
        print("    Has X in window:           %d" % cycles_has_x_in)
        print("    No X in window:            %d  (should be 0)" % cycles_pos_no_x)
        if cycles_x_not_found:
            print("    X not found (non-standard): %d" % cycles_x_not_found)
        if x_positions:
            x_sorted = sorted(x_positions)
            n = len(x_sorted)
            print("    X position (0=W.ct, 1=R.invoc-2e): "
                  "min=%.3f, median=%.3f, max=%.3f" % (
                      x_sorted[0], x_sorted[n//2], x_sorted[-1]))

        # Type distribution (per cycle)
        if type_counts:
            total_classified = sum(type_counts.values())
            print("\n  Anomaly type distribution (per cycle, %d classified):" % total_classified)
            for rt, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
                print("    %s: %d (%.1f%%)" % (rt, cnt, 100*cnt/total_classified))

    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Filter cascade analysis: skip rate -> anomaly rate decomposition')
    parser.add_argument('path', help='Results directory or config file')
    parser.add_argument('out_dir', nargs='?', help='Output directory (legacy mode)')
    parser.add_argument('--clock-err', type=int, default=100,
                        help='Clock sync error in us (default: 100)')
    parser.add_argument('--limit', type=int, default=0,
                        help='Process only first N transactions by invoc_ts')
    args = parser.parse_args()

    clock_err = args.clock_err

    if args.out_dir:
        # Legacy: python3 analysis.py <config_file> <out_dir> [--clock-err N]
        import json
        with open(args.path) as f:
            config = json.load(f)
        run_analysis(config, args.out_dir, clock_err, args.limit)
    else:
        # Auto-discover: python3 analysis.py <results_dir> [--clock-err N] [--limit N]
        experiments = find_experiment(args.path)
        if not experiments:
            sys.stderr.write('No experiments found under %s\n' % args.path)
            sys.exit(1)
        for i, (config, out_dir) in enumerate(experiments):
            if i > 0:
                print("\n" + "#"*70 + "\n")
            print("Config: %s" % os.path.basename(out_dir.rstrip('/out').rstrip('/')))
            run_analysis(config, out_dir, clock_err, args.limit)


if __name__ == "__main__":
    main()
