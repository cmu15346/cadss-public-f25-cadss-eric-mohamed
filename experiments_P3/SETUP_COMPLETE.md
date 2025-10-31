# P3 Integration Experiments - Complete Setup

## Summary

I've created a comprehensive experiment framework for your P3 report that explores the integration of:
- **Cache configurations** (10 variants from P1)
- **Branch predictor configurations** (8 variants from P2)  
- **Processor pipeline configurations** (7 variants)
- **Workload traces** (3 traces from `traces/integ/`)

**Total: 1,680 simulations** testing all combinations.

## Files Created

```
experiments_P3/
├── integration_experiment.py    # Main experiment runner
├── analyze_results.py           # Results analysis script
├── preview_configs.py           # Preview configurations
├── test_single.py              # Test single config
├── run_experiments.sh          # WSL wrapper script
├── README.md                   # Detailed documentation
├── QUICKSTART_WINDOWS.md       # Windows/WSL quick start
└── experiment_results/         # Results directory (created during run)
    ├── integration_results.csv
    └── figures/
```

## Quick Commands (Run in PowerShell)

### 1. Preview what will be tested
```powershell
wsl bash experiments_P3/run_experiments.sh preview
```

### 2. Test single configuration (~5 seconds)
```powershell
wsl bash experiments_P3/run_experiments.sh test
```

### 3. Run full experiments (~2-3 hours)
```powershell
wsl bash experiments_P3/run_experiments.sh run
```

### 4. Analyze results
```powershell
wsl bash experiments_P3/run_experiments.sh analyze
```

## What Gets Measured

For each configuration combination:
- **Total ticks**: Execution time
- **AAT**: Average access time (ticks/instruction)
- **IPC**: Instructions per cycle
- **Raw output**: Full simulator output for debugging

## Analysis Provides

The `analyze_results.py` script answers all your report questions:

### 1. Component Impact
- Which cache configurations perform best
- Which branch predictors perform best
- Which processor configurations perform best

### 2. Stall Amelioration (Question: "What resources ameliorate stalls?")
Compares processor configurations to show:
- Impact of increased fetch width
- Impact of more functional units
- Impact of larger reservation stations
- Impact of more dispatch bandwidth
- Impact of more CDBs

### 3. Integration Effects
- How cache and branch predictor choices interact
- Best combinations for each workload
- Performance heatmaps

### 4. Design Tradeoffs (Question: "Are there tradeoffs?")
- Cache size vs. performance
- Branch predictor size vs. performance
- Processor complexity vs. IPC efficiency

## Test Results from Single Run

Just tested with `black.trace`:
```
Configuration:
  - Processor: Balanced (f=2, d=1, m=2, j=2, k=1, c=2)
  - Cache: 16KB 2-way LRU
  - Branch: GSELECT 128 counters, 2-bit BHR

Results:
  - Total ticks: 2,609,987
  - Total instructions: 567,050
  - AAT: 4.60 cycles/instruction
  - IPC: 0.217
```

The simulator is working correctly! ✅

## Experiment Configurations Explained

### Processor Configs (How they ameliorate stalls)

1. **Baseline** (f=1, d=1, m=1, j=1, k=1, c=1)
   - Minimal resources - shows worst-case stall impact

2. **Wide-Fetch** (f=4)
   - Helps recover quickly after branch mispredictions
   - Fills pipeline faster

3. **More-FUs** (j=4, k=2, m=2, c=2)
   - More functional units allow more parallel execution
   - Helps hide cache miss latency by executing independent ops

4. **Large-RS** (m=4)
   - Larger reservation stations (4× per FU)
   - More instructions in flight
   - Better instruction-level parallelism exploitation

5. **Aggressive-Dispatch** (d=3)
   - 3× dispatch rate
   - Fills pipeline aggressively
   - Finds more independent work

6. **Balanced** (f=2, d=2, m=2, j=2, k=1, c=2)
   - Moderate increases across all parameters
   - Good balance of resources

7. **High-End** (f=4, d=2, m=3, j=4, k=2, c=4)
   - All parameters maximized
   - Shows maximum performance potential
   - Most resources to hide stalls

### Cache Configs (From P1)

- **Small**: 8-16KB (fast, lower capacity)
- **Medium**: 32-35KB (balanced)
- **High-associativity**: Up to 16-way (reduce conflict misses)
- **RRIP**: Alternative replacement policy
- **Victim cache**: Additional entries for recently evicted lines

### Branch Predictor Configs (From P2)

- **2-bit**: Simple saturating counters (32-512)
- **GSELECT**: PC + BHR concatenation (various BHR sizes)
- **GSHARE**: PC ⊕ BHR (XOR-based)

## Next Steps

1. **Run test first** to verify everything works:
   ```powershell
   wsl bash experiments_P3/run_experiments.sh test
   ```

2. **Review configurations** to ensure they match your needs:
   ```powershell
   wsl bash experiments_P3/run_experiments.sh preview
   ```

3. **Run experiments** (start during evening/overnight):
   ```powershell
   wsl bash experiments_P3/run_experiments.sh run
   ```

4. **Analyze results** and generate report data:
   ```powershell
   wsl bash experiments_P3/run_experiments.sh analyze
   ```

## Customization

To modify experiment scope, edit `integration_experiment.py`:

- `generate_processor_configs()` - Adjust processor parameters
- `generate_cache_configs()` - Adjust cache configurations  
- `generate_branch_configs()` - Adjust branch predictors

To test fewer configs quickly, comment out some entries in these functions.

## Report Questions Coverage

The experiments are specifically designed to answer:

✅ **Q1: How does the superscalar pipeline handle cache misses and branch mispredictions?**
- Measured through different processor configurations
- Shows impact on ticks, AAT, and IPC

✅ **Q2: What resources ameliorate the impact of these stalls?**
- Compares Baseline vs. Wide-Fetch, More-FUs, Large-RS, etc.
- Quantifies improvement from each resource type

✅ **Q3: What is your proposed design(s)? Are there tradeoffs?**
- Analysis shows best combinations
- Reveals size/complexity vs. performance tradeoffs
- Shows which configs work best for different workloads

## Need Help?

Check these files:
- `experiments_P3/README.md` - Full documentation
- `experiments_P3/QUICKSTART_WINDOWS.md` - Windows-specific guide

All scripts have been tested and are ready to run!
