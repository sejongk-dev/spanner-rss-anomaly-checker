"""
DSG-Based Anomaly Checker for Spanner-RSS

Builds a Direct Serialization Graph (DSG) from execution traces and
detects SS violations via cycle finding (Tarjan SCC + BFS shortest cycle).
"""

import json, os, sys, time
from typing import Optional, Iterator
from collections import defaultdict, deque

Timestamp = int
TxId = int


# ============================================================
# Transaction classes
# ============================================================

class Transaction:
    """Base transaction with fields common to DSG node representation."""
    is_rw: bool = False

    def __init__(self, tx_id: TxId, invoc_ts: Timestamp, resp_ts: Timestamp) -> None:
        self.id = tx_id
        self.invoc_ts = invoc_ts
        self.resp_ts = resp_ts
        self.reads: list[tuple[str, TxId]] = []
        self.write_keys_set: set[str] = set()


class RWTransaction(Transaction):
    is_rw = True

    def __init__(self, tx_id: TxId, invoc_ts: Timestamp, resp_ts: Timestamp,
                 commit_ts: Timestamp, commit_ts_id: int = 0,
                 write_keys: Optional[list[str]] = None,
                 read_keys: Optional[list[tuple[str, TxId]]] = None) -> None:
        super().__init__(tx_id, invoc_ts, resp_ts)
        self.commit_ts = commit_ts
        self.commit_ts_id = commit_ts_id
        self.write_keys_set = set(write_keys) if write_keys is not None else set()
        self.reads = read_keys if read_keys is not None else []


class ROTransaction(Transaction):
    is_rw = False

    def __init__(self, tx_id: TxId, invoc_ts: Timestamp, resp_ts: Timestamp,
                 reads: list[tuple[str, TxId]],
                 skipped_rws: list[tuple[TxId, list[str]]]) -> None:
        super().__init__(tx_id, invoc_ts, resp_ts)
        self.reads = reads
        self.skipped_rws = skipped_rws  # [(tx_id, [conflict_keys])]


# ============================================================
# Phase 0: Parse logs
# ============================================================

def get_committed_transactions(config, local_out_directory, run) -> tuple[list[RWTransaction], list[ROTransaction]]:
    rw_list, ro_list = [], []

    for client in config["clients"]:
        client_dir = client
        for k in range(config["client_processes_per_client_node"]):
            client_out_file = os.path.join(local_out_directory,
                                           client_dir,
                                           '%s-%d-stdout-%d.log' % (client, k, run))
            with open(client_out_file) as f:
                ops = f.readlines()
                for op in ops:
                    if not op.startswith(('#RWC', '#ROC')):
                        continue

                    opCols = op.strip().split(',')

                    if opCols[0] == '#RWC':
                        tx_id, invoc_ts, resp_ts, commit_ts = list(map(int, opCols[1:5]))
                        commit_ts_id = int(opCols[5]) if len(opCols) > 5 and opCols[5].strip() else 0
                        write_keys_str = opCols[6].strip() if len(opCols) > 6 else ""
                        write_keys = write_keys_str.split('+') if write_keys_str else []
                        read_keys = []
                        if len(opCols) > 7 and opCols[7].strip():
                            for entry in opCols[7].strip().split('/')[:-1]:
                                parts = entry.split(':')
                                read_keys.append((parts[0], int(parts[1])))
                        rw_list.append(RWTransaction(tx_id, invoc_ts, resp_ts, commit_ts,
                                                     commit_ts_id, write_keys, read_keys))

                    elif opCols[0] == '#ROC':
                        tx_id, invoc_ts, resp_ts = list(map(int, opCols[1:4]))
                        reads = []
                        if opCols[4].strip():
                            reads = [tuple([int(e) if i > 0 else e for i, e in enumerate(read_str.split(':'))])
                                     for read_str in opCols[4].strip().split('/')[:-1]]
                        skipped_rws = []
                        if len(opCols) > 5 and opCols[5].strip():
                            for entry in opCols[5].strip().split('/')[:-1]:
                                parts = entry.split(':')
                                s_tx_id = int(parts[0])
                                s_keys = parts[1].split('+') if len(parts) > 1 and parts[1] else []
                                skipped_rws.append((s_tx_id, s_keys))
                        ro_list.append(ROTransaction(tx_id, invoc_ts, resp_ts, reads, skipped_rws))

    return rw_list, ro_list


# ============================================================
# Phase 1–5: DSG Checker
# ============================================================

class DSGChecker:
    def __init__(self, rw_list: list[RWTransaction], ro_list: list[ROTransaction],
                 clock_err: int = 0) -> None:
        self.clock_err = clock_err
        self.rw_list = rw_list
        self.ro_list = ro_list
        self.all_txs: list[Transaction] = list(rw_list) + list(ro_list)

        # Phase 1: Index structures
        self.tx_by_id: dict[TxId, Transaction] = {}
        self.key_writers: dict[str, list[RWTransaction]] = defaultdict(list)
        self.next_writer_of: dict[tuple[str, TxId], Optional[TxId]] = {}
        self.dep_adj: dict[TxId, set[TxId]] = defaultdict(set)

        # RT edges (OROCHI transitive reduction)
        self.rt_adj: dict[TxId, list[TxId]] = {}

        self.timings: dict[str, float] = {}
        self.stats: dict[str, int] = {}

        t0 = time.time()
        self._build_indices()
        self.timings['phase1_index'] = time.time() - t0

        # Phase 2: Dep edges
        t0 = time.time()
        self._build_dep_edges()
        self.timings['phase2_dep_edges'] = time.time() - t0

        # Phase 2.5: OROCHI RT edges
        t0 = time.time()
        self._build_rt_edges_orochi()
        self.timings['phase2_5_rt_orochi'] = time.time() - t0

    # ── Phase 1 ──

    def _build_indices(self) -> None:
        # tx_by_id
        for tx in self.all_txs:
            self.tx_by_id[tx.id] = tx

        # key_writers: sorted by (commit_ts, commit_ts_id)
        for rw in self.rw_list:
            for key in rw.write_keys_set:
                self.key_writers[key].append(rw)
        for key in self.key_writers:
            self.key_writers[key].sort(key=lambda rw: (rw.commit_ts, rw.commit_ts_id))

        # next_writer_of: O(W) construction, O(1) lookup
        for key, writers in self.key_writers.items():
            for i in range(len(writers)):
                next_id = writers[i + 1].id if i + 1 < len(writers) else None
                self.next_writer_of[(key, writers[i].id)] = next_id


    # ── Phase 2 ──

    def _build_dep_edges(self) -> None:
        # WW edges
        for key, writers in self.key_writers.items():
            for i in range(len(writers) - 1):
                self.dep_adj[writers[i].id].add(writers[i + 1].id)

        # WR edges
        for tx in self.all_txs:
            for key, writer_id in tx.reads:
                if writer_id in self.tx_by_id:
                    self.dep_adj[writer_id].add(tx.id)

        # RW anti-dependency edges
        for tx in self.all_txs:
            for key, writer_id in tx.reads:
                next_w_id = self.next_writer_of.get((key, writer_id))
                if next_w_id is not None and next_w_id != tx.id:
                    self.dep_adj[tx.id].add(next_w_id)

    # ── RT edges ──

    def _build_rt_edges_orochi(self) -> None:
        """OROCHI Figure 6: CreateTimePrecedenceGraph (Tan et al., SOSP'17).

        Streaming frontier-based algorithm that computes the transitive
        reduction of the time-precedence partial order in O(n + Z) time.

        Frontier = set of latest, mutually concurrent completed transactions.
        On REQUEST(v): add edges from all frontier members → v.
        On RESPONSE(u): evict u's parents from frontier, add u to frontier.
        """
        events: list[tuple[int, int, int, TxId]] = []
        for tx in self.all_txs:
            resp_adj = tx.resp_ts + 2 * self.clock_err
            # (time, priority, type, tx_id)
            # priority: 0=REQ first at same time, 1=RESP after
            # type: 0=REQ, 1=RESP
            events.append((tx.invoc_ts, 0, 0, tx.id))
            events.append((resp_adj, 1, 1, tx.id))
        events.sort()

        frontier: set[TxId] = set()
        parents: dict[TxId, set[TxId]] = {}
        rt_adj = self.rt_adj
        n_edges = 0

        for _, _, etype, tx_id in events:
            if etype == 0:  # REQ
                if frontier:
                    for r in frontier:
                        if r in rt_adj:
                            rt_adj[r].append(tx_id)
                        else:
                            rt_adj[r] = [tx_id]
                    n_edges += len(frontier)
                    parents[tx_id] = set(frontier)
                else:
                    parents[tx_id] = set()
            else:  # RESP
                parent_set = parents.pop(tx_id, None)
                if parent_set:
                    frontier -= parent_set
                frontier.add(tx_id)

        self.stats['rt_orochi_edges'] = n_edges

    def _rt_successors(self, u: Transaction) -> Iterator[Transaction]:
        """Yield RT successors of u from OROCHI transitive reduction."""
        for v_id in self.rt_adj.get(u.id, ()):
            yield self.tx_by_id[v_id]

    def _outgoing(self, u_id: TxId) -> Iterator[TxId]:
        """All outgoing neighbors of u: dep edges (explicit) + RT edges (implicit)."""
        # Dep edges
        for v_id in self.dep_adj.get(u_id, set()):
            yield v_id
        # RT edges (may duplicate dep edges; Tarjan/BFS handle duplicates fine)
        for v in self._rt_successors(self.tx_by_id[u_id]):
            yield v.id

    # ── Phase 3: Tarjan SCC ──

    def _tarjan_scc(self, all_node_ids: list[TxId]) -> list[list[TxId]]:
        index_counter = 0
        stack: list[TxId] = []
        on_stack: set[TxId] = set()
        node_index: dict[TxId, int] = {}
        node_lowlink: dict[TxId, int] = {}
        sccs: list[list[TxId]] = []

        for start in all_node_ids:
            if start in node_index:
                continue
            call_stack: list[tuple[TxId, Iterator[TxId], bool]] = [
                (start, iter(self._outgoing(start)), True)
            ]
            while call_stack:
                v, neighbors, first_visit = call_stack[-1]
                if first_visit:
                    node_index[v] = node_lowlink[v] = index_counter
                    index_counter += 1
                    stack.append(v)
                    on_stack.add(v)
                    call_stack[-1] = (v, neighbors, False)

                recurse = False
                for w in neighbors:
                    if w not in node_index:
                        call_stack.append((w, iter(self._outgoing(w)), True))
                        recurse = True
                        break
                    elif w in on_stack:
                        node_lowlink[v] = min(node_lowlink[v], node_index[w])

                if not recurse:
                    if node_lowlink[v] == node_index[v]:
                        scc: list[TxId] = []
                        while True:
                            w = stack.pop()
                            on_stack.remove(w)
                            scc.append(w)
                            if w == v:
                                break
                        sccs.append(scc)
                    call_stack.pop()
                    if call_stack:
                        parent_v = call_stack[-1][0]
                        node_lowlink[parent_v] = min(
                            node_lowlink[parent_v], node_lowlink[v]
                        )

        return sccs

    # ── Phase 4: BFS shortest cycle ──

    def _find_shortest_cycle(self, scc_set: set[TxId]) -> Optional[list[TxId]]:
        best_cycle: Optional[list[TxId]] = None

        def scc_outgoing(v: TxId) -> Iterator[TxId]:
            for w in self._outgoing(v):
                if w in scc_set:
                    yield w

        for start in scc_set:
            parent: dict[TxId, TxId] = {}
            queue: deque[TxId] = deque()

            # Seed: direct successors of start
            for w in scc_outgoing(start):
                if w == start:
                    return [start]  # self-loop
                if w not in parent:
                    parent[w] = start
                    queue.append(w)

            # BFS
            found = False
            while queue and not found:
                v = queue.popleft()
                for w in scc_outgoing(v):
                    if w == start:
                        path: list[TxId] = []
                        node = v
                        while node != start:
                            path.append(node)
                            node = parent[node]
                        path.append(start)
                        cycle = list(reversed(path))

                        if best_cycle is None or len(cycle) < len(best_cycle):
                            best_cycle = cycle
                        found = True
                        break

                    if w not in parent:
                        parent[w] = v
                        queue.append(w)

            if best_cycle and len(best_cycle) == 2:
                break  # minimum possible directed cycle length

        return best_cycle

    # ── Phase 4b: Find all simple cycles (Johnson's algorithm) ──

    def _find_all_cycles(self, scc_set: set[TxId],
                         max_cycles: int = 10000) -> list[list[TxId]]:
        """Find all simple directed cycles within an SCC using Johnson's algorithm.

        Returns a list of cycles, each cycle being a list of node IDs in order.
        Stops early if max_cycles is reached (safety limit for large SCCs).
        """
        # Build local adjacency restricted to SCC
        nodes = sorted(scc_set)
        adj: dict[TxId, list[TxId]] = {n: [] for n in nodes}
        for n in nodes:
            for w in self._outgoing(n):
                if w in scc_set and w != n:
                    if w not in adj[n]:  # deduplicate
                        adj[n].append(w)

        all_cycles: list[list[TxId]] = []
        node_set = set(nodes)

        def _johnson_unblock(u: TxId, blocked: set[TxId],
                             block_map: dict[TxId, set[TxId]]) -> None:
            stack = [u]
            while stack:
                w = stack.pop()
                if w in blocked:
                    blocked.remove(w)
                    for v in block_map.get(w, set()):
                        stack.append(v)
                    block_map[w] = set()

        for i, s in enumerate(nodes):
            # Only consider subgraph induced by nodes[i:]
            sub = set(nodes[i:])
            blocked: set[TxId] = set()
            block_map: dict[TxId, set[TxId]] = {n: set() for n in sub}
            path: list[TxId] = [s]
            blocked.add(s)

            # Iterative DFS with explicit stack
            # Stack entries: (node, neighbor_iterator, found_cycle_through_here)
            stack: list[tuple[TxId, int, bool]] = [(s, 0, False)]

            while stack:
                v, ni, found = stack[-1]
                neighbors = [w for w in adj.get(v, []) if w in sub]

                if ni < len(neighbors):
                    w = neighbors[ni]
                    stack[-1] = (v, ni + 1, found)

                    if w == s:
                        # Found a cycle
                        all_cycles.append(list(path))
                        if len(all_cycles) >= max_cycles:
                            return all_cycles
                        stack[-1] = (v, ni + 1, True)
                    elif w not in blocked:
                        blocked.add(w)
                        path.append(w)
                        stack.append((w, 0, False))
                else:
                    # Backtrack
                    if found:
                        _johnson_unblock(v, blocked, block_map)
                    else:
                        for w in neighbors:
                            if w in sub:
                                block_map.setdefault(w, set()).add(v)
                    path.pop()
                    stack.pop()
                    if stack:
                        # Propagate found flag upward
                        pv, pni, pfound = stack[-1]
                        stack[-1] = (pv, pni, pfound or found)

            node_set.discard(s)

        return all_cycles

    # ── Phase 5: Classification ──

    def _classify_edge(self, u_id: TxId, v_id: TxId) -> set[str]:
        u, v = self.tx_by_id[u_id], self.tx_by_id[v_id]
        types: set[str] = set()

        # WW
        if u.is_rw and v.is_rw:
            for k in u.write_keys_set & v.write_keys_set:
                if self.next_writer_of.get((k, u.id)) == v.id:
                    types.add('WW')
                    break

        # WR
        if u.is_rw:
            for k, wid in v.reads:
                if wid == u.id:
                    types.add('WR')
                    break

        # RW anti-dep
        if v.is_rw:
            for k, wid in u.reads:
                if self.next_writer_of.get((k, wid)) == v.id:
                    types.add('RW')
                    break

        # RT (sound: u definitely finished before v started)
        if u.resp_ts + self.clock_err < v.invoc_ts - self.clock_err:
            types.add('RT')

        return types

    def _explain_edge(self, u_id: TxId, v_id: TxId) -> list[str]:
        """Return human-readable justification for each edge type."""
        u, v = self.tx_by_id[u_id], self.tx_by_id[v_id]
        reasons: list[str] = []

        # WW
        if u.is_rw and v.is_rw:
            for k in u.write_keys_set & v.write_keys_set:
                if self.next_writer_of.get((k, u.id)) == v.id:
                    reasons.append("WW on key=%s: u.commit=%d → v.commit=%d" % (
                        k, u.commit_ts, v.commit_ts))

        # WR
        if u.is_rw:
            for k, wid in v.reads:
                if wid == u.id:
                    reasons.append("WR on key=%s: v reads from u (writer=%d)" % (k, u.id))

        # RW anti-dep
        if v.is_rw:
            for k, wid in u.reads:
                if self.next_writer_of.get((k, wid)) == v.id:
                    writer_tx = self.tx_by_id.get(wid)
                    w_commit = writer_tx.commit_ts if writer_tx and writer_tx.is_rw else '?'
                    reasons.append(
                        "RW on key=%s: u reads from writer=%d (commit=%s), "
                        "v is next_writer (commit=%d)" % (k, wid, w_commit, v.commit_ts))

        # RT (sound: u definitely finished before v started)
        if u.resp_ts + self.clock_err < v.invoc_ts - self.clock_err:
            reasons.append("RT: u.resp=%d + %d < v.invoc=%d - %d  (gap=%d us)" % (
                u.resp_ts, self.clock_err, v.invoc_ts, self.clock_err,
                v.invoc_ts - u.resp_ts))

        return reasons

    def _classify_cycle(self, cycle: list[TxId]) -> list[tuple[TxId, TxId, set[str]]]:
        """Classify edges in the cycle (for display). Returns edge_info only."""
        edge_info: list[tuple[TxId, TxId, set[str]]] = []
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            types = self._classify_edge(u, v)
            edge_info.append((u, v, types))
        return edge_info

    def _classify_scc_anomaly(self, scc_set: set[TxId]) -> list[dict]:
        """Classify anomaly patterns anchored on (RO, skipped_RW) pairs.

        For each RO in the SCC that skipped an RW also in the SCC:
          1. Verify the anti-dependency exists
          2. BFS from skipped_RW through all edges (dep + RT) within the SCC
          3. Find the first node X where X.resp_ts + 2ε < RO.invoc_ts (sound RT)
          4. Classify based on X's type
          5. Count RT edges in the path to determine multi-RT

        Falls back to 'other' if no (RO, skipped_RW) pattern is found
        (e.g. pure RW cycles indicating serializability violations).
        """
        anomaly_types: list[dict] = []

        for tx_id in scc_set:
            tx = self.tx_by_id[tx_id]
            if tx.is_rw or not hasattr(tx, 'skipped_rws'):
                continue
            ro = tx

            for skipped_rw_id, conflict_keys in ro.skipped_rws:
                if skipped_rw_id not in scc_set:
                    continue
                skipped_rw = self.tx_by_id.get(skipped_rw_id)
                if skipped_rw is None:
                    continue

                # Verify anti-dep exists
                antidep_keys = [k for k, wid in ro.reads
                                if self.next_writer_of.get((k, wid)) == skipped_rw_id]
                if not antidep_keys:
                    continue

                # BFS from skipped_RW through all edges (dep + RT) within SCC
                # Looking for X where X.resp_ts + 2*clock_err < RO.invoc_ts
                # (sound: X definitely finished before RO started)
                found_x = None
                rt_hops = 0

                # Check skipped_RW itself first (zero-hop)
                if skipped_rw.resp_ts + 2 * self.clock_err < ro.invoc_ts:
                    found_x = skipped_rw
                    rt_hops = 0
                else:
                    visited = {skipped_rw_id}
                    queue: deque[tuple[TxId, int]] = deque([(skipped_rw_id, 0)])
                    while queue:
                        node_id, rt_count = queue.popleft()
                        for neighbor_id in self._outgoing(node_id):
                            if neighbor_id not in scc_set or neighbor_id in visited:
                                continue
                            visited.add(neighbor_id)
                            neighbor = self.tx_by_id[neighbor_id]
                            # Count pure-RT edges (no dep justification)
                            has_dep = neighbor_id in self.dep_adj.get(node_id, set())
                            new_rt = rt_count + (0 if has_dep else 1)
                            if neighbor.resp_ts + 2 * self.clock_err < ro.invoc_ts:
                                found_x = neighbor
                                rt_hops = new_rt
                                break
                            queue.append((neighbor_id, new_rt))
                        if found_x is not None:
                            break

                if found_x is None:
                    continue

                # Classify based on X's type
                x = found_x
                # Total RT in cycle: rt_hops (skipped_RW → X) + 1 (X → RO)
                total_rt = rt_hops + 1

                if x.is_rw:
                    conflict = x.write_keys_set & set(k for k, _ in ro.reads)
                    if conflict:
                        rt_type = 'conflicting RW->RO (RSS should prevent)'
                    else:
                        rt_type = 'non-conflicting RW->RO'
                else:
                    rt_type = 'RO->RO'

                anomaly_types.append({
                    'rt_type': rt_type,
                    'rt_source': x.id,
                    'skipping_ro': ro.id,
                    'skipped_rw': skipped_rw_id,
                    'is_skip': True,
                    'antidep_keys': antidep_keys,
                    'rt_count': total_rt,
                })

        # Fallback: no (RO, skipped_RW) pattern found
        if not anomaly_types:
            anomaly_types.append({
                'rt_type': 'other',
                'rt_source': None,
                'skipping_ro': None,
                'skipped_rw': None,
                'is_skip': False,
                'antidep_keys': [],
                'rt_count': 0,
            })

        return anomaly_types

    # ── Main entry point ──

    def find_anomalies(self) -> list[dict]:
        all_ids = list(self.tx_by_id.keys())

        # Phase 3: Tarjan SCC
        t0 = time.time()
        sccs = self._tarjan_scc(all_ids)
        self.timings['phase3_tarjan'] = time.time() - t0

        non_trivial = [s for s in sccs if len(s) > 1]
        self.stats['scc_count'] = len(sccs)
        self.stats['non_trivial_scc_count'] = len(non_trivial)

        # Phase 4–5: classify per non-trivial SCC
        # - cycle: one shortest cycle for display/debugging (not used in analysis)
        # - anomaly_types: all (R, W, X) cycle patterns = analysis unit (one per skip pair)
        t0 = time.time()
        anomalies = []
        for scc in non_trivial:
            scc_set = set(scc)
            cycle = self._find_shortest_cycle(scc_set)  # display only
            if cycle:
                edge_info = self._classify_cycle(cycle)
                anomaly_types = self._classify_scc_anomaly(scc_set)
                all_cycles = self._find_all_cycles(scc_set)
                anomalies.append({
                    'cycle': cycle,
                    'edge_info': edge_info,
                    'anomaly_types': anomaly_types,
                    'all_cycles': all_cycles,
                    'scc_size': len(scc),
                })
        self.timings['phase4_5_bfs_classify'] = time.time() - t0

        return anomalies


# ============================================================
# Output
# ============================================================

def print_anomalies(anomalies: list[dict], checker: DSGChecker) -> None:
    n_rw = len(checker.rw_list)
    n_ro = len(checker.ro_list)
    n_dep = sum(len(v) for v in checker.dep_adj.values())
    n_next_writer = len(checker.next_writer_of)
    n_cycles = sum(len(a['anomaly_types']) for a in anomalies)
    print("Transactions: %d RW, %d RO (%d total)" % (n_rw, n_ro, n_rw + n_ro))
    print("Dep edges: %d, next_writer index: %d entries" % (n_dep, n_next_writer))
    print("SS violations: %d anomaly cycles in %d SCCs" % (n_cycles, len(anomalies)))

    # Timings & stats
    t = checker.timings
    s = checker.stats

    # RT mode
    print("RT mode: OROCHI (time precedence graph, %d edges)" % s.get('rt_orochi_edges', 0))
    print("\nTimings:")
    print("  Phase 1 (index):       %.3fs" % t.get('phase1_index', 0))
    print("  Phase 2 (dep edges):   %.3fs" % t.get('phase2_dep_edges', 0))
    if 'phase2_5_rt_orochi' in t:
        print("  Phase 2.5 (OROCHI RT): %.3fs" % t['phase2_5_rt_orochi'])
    print("  Phase 3 (Tarjan SCC):  %.3fs  [%d SCCs, %d non-trivial]" % (
        t.get('phase3_tarjan', 0),
        s.get('scc_count', 0),
        s.get('non_trivial_scc_count', 0)))
    print("  Phase 4-5 (BFS+class): %.3fs" % t.get('phase4_5_bfs_classify', 0))
    print()

    # Summary counts
    type_counts: dict[str, int] = {}
    multi_rt_count = 0
    for a in anomalies:
        for at in a['anomaly_types']:
            rt = at['rt_type']
            type_counts[rt] = type_counts.get(rt, 0) + 1
            if at.get('rt_count', 0) > 1:
                multi_rt_count += 1
    if type_counts:
        print("Anomaly types:")
        for rt, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            print("  %s: %d" % (rt, cnt))
        if multi_rt_count:
            print("  (multi-RT: %d)" % multi_rt_count)
        print()

    for i, a in enumerate(anomalies):
        cycle = a['cycle']
        edge_info = a['edge_info']
        anomaly_types = a['anomaly_types']
        scc_size = a['scc_size']

        print("=== Anomaly %d (SCC size=%d, shortest cycle length=%d) ===" % (i + 1, scc_size, len(cycle)))

        # Anomaly pattern
        for at in anomaly_types:
            if at['rt_type'] == 'other':
                print("  Pattern: other (no RO skip pattern; possible serializability violation)")
            else:
                src = checker.tx_by_id[at['rt_source']]
                src_label = "RW" if src.is_rw else "RO"
                rt_label = "multi-RT (%d)" % at['rt_count'] if at['rt_count'] > 1 else "single-RT"
                print("  RSS pattern: %s(%d) -[RT]-> RO(%d) -[RW anti-dep, keys=%s]-> RW(%d)%s" % (
                    src_label, at['rt_source'], at['skipping_ro'],
                    at['antidep_keys'], at['skipped_rw'],
                    " [SKIP]" if at['is_skip'] else " [NOT IN SKIP LOG]"))
                print("  RSS type: %s (%s)" % (at['rt_type'], rt_label))

        print("  Shortest cycle edges (one possible cycle, for debugging):")
        for u_id, v_id, types in edge_info:
            u = checker.tx_by_id[u_id]
            v = checker.tx_by_id[v_id]
            u_label = "RW" if u.is_rw else "RO"
            v_label = "RW" if v.is_rw else "RO"
            types_str = "+".join(sorted(types))
            print("    %s(%d) -[%s]-> %s(%d)" % (u_label, u_id, types_str, v_label, v_id))
            for reason in checker._explain_edge(u_id, v_id):
                print("      %s" % reason)

        # Print transaction details
        print("  Transaction details:")
        printed = set()
        for u_id, v_id, _ in edge_info:
            for tid in (u_id, v_id):
                if tid in printed:
                    continue
                printed.add(tid)
                tx = checker.tx_by_id[tid]
                if tx.is_rw:
                    print("    RW(%d): invoc=%d, resp=%d, commit=%d" % (
                        tx.id, tx.invoc_ts, tx.resp_ts, tx.commit_ts))
                    print("      writes=%s" % sorted(tx.write_keys_set))
                    print("      reads=%s" % tx.reads)
                else:
                    print("    RO(%d): invoc=%d, resp=%d" % (
                        tx.id, tx.invoc_ts, tx.resp_ts))
                    print("      reads=%s" % tx.reads)
                    if tx.skipped_rws:
                        print("      skipped_rws=%s" % tx.skipped_rws)
        print()


# ============================================================
# Auto-discover experiment results
# ============================================================

def find_experiment(results_dir: str) -> list[tuple[dict, str]]:
    """Find all (config, out_directory) pairs under a results directory.

    Experiment layout:
        results_dir/
          <timestamp>/
            <timestamp>/
              <name>.json       ← config
              out/               ← client logs
    """
    experiments = []
    for root, dirs, files in os.walk(results_dir):
        if 'out' in dirs:
            jsons = [f for f in files if f.endswith('.json') and f != 'network.json']
            if jsons:
                config_path = os.path.join(root, jsons[0])
                out_path = os.path.join(root, 'out')
                with open(config_path) as f:
                    config = json.load(f)
                experiments.append((config, out_path))
    return experiments


# ============================================================
# Main
# ============================================================

def apply_limit(rw_list: list[RWTransaction], ro_list: list[ROTransaction],
                limit: int) -> tuple[list[RWTransaction], list[ROTransaction]]:
    """Keep only the first `limit` transactions by invoc_ts."""
    all_txs: list[Transaction] = list(rw_list) + list(ro_list)
    all_txs.sort(key=lambda tx: tx.invoc_ts)
    keep_ids = set(tx.id for tx in all_txs[:limit])
    return (
        [tx for tx in rw_list if tx.id in keep_ids],
        [tx for tx in ro_list if tx.id in keep_ids],
    )


def run_checker(config: dict, out_dir: str, clock_err: int,
                limit: int = 0) -> None:
    for run in range(config.get("num_experiment_runs", 1)):
        print("=== Run %d ===" % run)
        t0 = time.time()
        rw_list, ro_list = get_committed_transactions(config, out_dir, run)
        parse_time = time.time() - t0
        print("Parsed: %d RW, %d RO (%.3fs)" % (len(rw_list), len(ro_list), parse_time))
        if limit > 0:
            rw_list, ro_list = apply_limit(rw_list, ro_list, limit)
            print("After --limit %d: %d RW, %d RO" % (limit, len(rw_list), len(ro_list)))

        checker = DSGChecker(rw_list, ro_list, clock_err)
        anomalies = checker.find_anomalies()
        print_anomalies(anomalies, checker)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='DSG-Based Anomaly Checker for Spanner-RSS')
    parser.add_argument('path', help='Results directory or config file')
    parser.add_argument('out_dir', nargs='?', help='Output directory (legacy mode)')
    parser.add_argument('--clock-err', type=int, default=100,
                        help='Clock sync error in us (default: 100)')
    parser.add_argument('--limit', type=int, default=0,
                        help='Process only first N transactions by invoc_ts')
    args = parser.parse_args()

    clock_err = args.clock_err

    if args.out_dir:
        # Legacy: python3 checker.py <config_file> <out_dir> [--clock-err N]
        with open(args.path) as f:
            config = json.load(f)
        run_checker(config, args.out_dir, clock_err, args.limit)
    else:
        # Auto-discover: python3 checker.py <results_dir> [--clock-err N] [--limit N]
        experiments = find_experiment(args.path)
        if not experiments:
            sys.stderr.write('No experiments found under %s\n' % args.path)
            sys.exit(1)
        for config, out_dir in experiments:
            print("Config: clients=%s, clock_err=%dus" % (config["clients"], clock_err))
            run_checker(config, out_dir, clock_err, args.limit)


if __name__ == "__main__":
    main()
