# Spanner-RSS Anomaly Checker

An offline anomaly checker that detects strict serializability (SS) violations in [Spanner-RSS](https://dl.acm.org/doi/10.1145/3477132.3483566) execution traces. It builds a Direct Serialization Graph (DSG) from transaction logs, finds cycles via Tarjan SCC decomposition and Johnson's algorithm, and structurally explains *why* anomalies arise through multi-stage cascading filters.

## Background

Spanner-RSS relaxes Spanner's strict serializability to Regular Sequential Serializability (RSS), allowing read-only transactions to observe slightly stale snapshots in exchange for lower tail latency. While RSS permits certain reorderings that SS forbids, not all such reorderings lead to actual anomalies. This checker systematically identifies which execution traces contain genuine SS-violation cycles and decomposes the conditions that produce them.

## Cascading filters

The checker implements 4-stage cascading filters that decomposes skip pairs (potential anomaly sources) into actual anomaly cycles:

```
C1 (Skip)  -->  C2 (Anti-dep)  -->  C3 (Window)  -->  C4 (Dependency-reachability)
```

| Stage | Condition | Description |
|-------|-----------|-------------|
| **C1** | Skip pair exists | RO transaction reads a version that was overwritten by a concurrent RW transaction (W.commit_ts > R.snapshot_ts) |
| **C2** | Valid anti-dependency | The skip pair has a valid RW anti-dependency edge in the DSG |
| **C3** | Positive vulnerability window | W.commit_ts < R.invoc_ts - 2 * clock_err (Theorem C3: every SS-violation cycle must contain at least one such pair) |
| **C4** | Dependency-reachability | A DSG successor X of W satisfies X.resp_ts < R.invoc_ts - 2 * clock_err, closing the cycle |

## Usage

### Prerequisites

- Python 3.8+
- The checker requires Spanner-RSS execution traces (transaction logs with timestamps and read/write sets)

### Running the Checker

```bash
# Auto-discover all experiments under a results directory
python3 checker/analysis.py <results_dir> [--clock-err N] [--limit N]

# Single experiment (legacy mode)
python3 checker/analysis.py <config_file> <out_dir> [--clock-err N]
```

**Options:**
- `--clock-err N`: Clock synchronization error in microseconds (default: 100)
- `--limit N`: Process only the first N transactions by invocation timestamp (0 = no limit)

### Output

The checker outputs:
- **Cacading filter table**: Pair counts at each stage (C1 through C4)
- **Vulnerability window distribution**: Statistics (min, max, mean, percentiles) for positive and negative windows
- **Cycle analysis**: Total cycles found, theorem validation results, and anomaly type distribution (Type 1: RW->RO, Type 2: RO->RO)

## Building the Spanner-RSS System

This repository also contains the Spanner-RSS system implementation used to generate the execution traces.

### Tool Versions

* cmake v3.10.2
* gcc/g++ v7.5.0
* python v3.6.9
* gnuplot v5.2

### Running Experiments

Experiments can run on any cluster settings with multiple machines.

1. Clone the repository with submodules:
   ```
   git clone --recursive <repo-url>
   ```

2. Build the C++ benchmark and server:
   ```
   cd src/ && mkdir build && cd build
   cmake .. && make
   ```

3. Install dependencies:
   ```
   sudo apt update && sudo apt install -y python3-numpy gnuplot
   ```

4. Update the experiment config (`project_name`, `experiment_name`, `base_local_exp_directory`, etc.)

5. Run experiments:
   ```
   python3 experiments/run_multiple_experiments.py <config.json>
   ```

## References

- J. Helt, et al. "Regular Sequential Serializability and Regular Sequential Consistency." SOSP 2021. [Paper](https://dl.acm.org/doi/10.1145/3477132.3483566)
- Tan, Cheng, et al. "The efficient server audit problem, deduplicated re-execution, and the web." SOSP 2017. [Paper](https://dl.acm.org/doi/pdf/10.1145/3132747.3132760)
- Google. "Spanner: Google's Globally-Distributed Database." TOCS 2013. [Paper](https://dl.acm.org/doi/abs/10.1145/2491245)
- I. Zhang et al. "Building Consistent Transactions with Inconsistent Replication (TAPIR)." SOSP 2015. [Paper](https://dl.acm.org/doi/10.1145/2815400.2815404)

## Authors

**Original Spanner-RSS**: Jeffrey Helt, Amit Levy, Wyatt Lloyd (Princeton), Matthew Burke (Cornell)

**Anomaly Checker**: Sejong Kim, Yon Dohn Chung (Korea University)