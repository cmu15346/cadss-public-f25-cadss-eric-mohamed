# P3 Integration Experiments

This directory contains scripts to run integration experiments combining cache, branch predictor, and processor configurations for the P3 report.

## Files

- **`integration_experiment.py`**: Main experiment script that runs all combinations
- **`analyze_results.py`**: Analysis script to interpret results and answer report questions
- **`preview_configs.py`**: Preview configurations before running experiments
- **`README.md`**: This file

## Quick Start

### 1. Preview Configurations (Optional)

See what configurations will be tested:

```bash
python experiments_P3/preview_configs.py
```

### 2. Run Experiments

Make sure the simulator is built first:

```bash
cmake .
make
```

Then run the experiments (this may take a while):

```bash
python experiments_P3/integration_experiment.py
```

### 3. Analyze Results

Once experiments complete, analyze the data:

```bash
python experiments_P3/analyze_results.py
```

## What the Experiments Test

### Processor Configurations (7 variants)
- **Baseline**: Minimal resources (f=1, d=1, m=1, j=1, k=1, c=1)
- **Wide-Fetch**: Increased fetch width (f=4)
- **More-FUs**: More functional units (j=4, k=2)
- **Large-RS**: Larger reservation stations (m=4)
- **Aggressive-Dispatch**: Higher dispatch rate (d=3)
- **Balanced**: All parameters moderately increased
- **High-End**: All parameters maximized

### Cache Configurations (10 variants)
- Small caches (16KB): Direct-mapped, 2-way, 4-way
- Medium caches (32KB): LRU and RRIP variants
- Large caches (64KB): 4-way and 8-way
- Victim cache variants

### Branch Predictor Configurations (8 variants)
- 2-bit predictors: Small (32), Medium (128), Large (512 counters)
- GSELECT: Various BHR sizes (2, 4, 6 bits)
- GSHARE: Small and large variants

### Traces
Uses traces from `traces/integ/`:
- `black.trace`: ~13.6 MB
- `fluid.trace`: ~1.2 GB (large workload)
- `ls.trace`: ~22.1 MB

## Output

Results are saved to:
- `experiment_results/integration_results.csv`: Raw data
- `experiment_results/figures/*.png`: Visualization plots (if matplotlib available)

## Analysis Output

The analysis script provides:

1. **Cache Configuration Impact**: Best cache designs
2. **Branch Predictor Impact**: Best predictor designs
3. **Processor Pipeline Impact**: Best processor configurations
4. **Resource Impact**: Which resources help hide stalls
5. **Component Interactions**: How cache and branch configs interact
6. **Design Tradeoffs**: Size vs. performance analysis
7. **Workload Characteristics**: Performance by trace
8. **Executive Summary**: Overall best configuration

## Report Questions Addressed

The experiments are designed to answer:

1. **How does the superscalar pipeline handle cache misses and branch mispredictions?**
   - Measured by comparing different processor configurations with varying resources

2. **What resources ameliorate the impact of these stalls?**
   - Analyzed by comparing: fetch width, # of FUs, RS size, dispatch rate, # of CDBs
   - Shows % improvement of each resource vs. baseline

3. **What are the design tradeoffs?**
   - Size vs. performance for cache
   - Counters vs. accuracy for branch predictor
   - Complexity vs. IPC for processor pipeline

## Notes

- Total experiments: 7 processors × 10 caches × 8 branches × 3 traces = 1,680 runs
- Each experiment measures: total ticks, AAT (ticks/instruction), IPC
- Failed simulations are automatically filtered out in analysis
- Large fluid.trace may take longer to simulate
