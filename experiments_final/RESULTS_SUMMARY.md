# Branch Predictor Comparison: Experiment Results Summary

## Overview

Successfully completed comprehensive comparison of **Perceptron-based** branch predictors (`final-project/`) vs **Classic** predictors (`my-branch/`) under fair storage budget constraints.

---

## Key Findings

### Overall Performance (156 matched pairs tested)
- **Perceptron wins: 66.7%** (104/156 configurations)
- **Classic wins: 33.3%** (52/156 configurations)
- **Average accuracy improvement: +1.05%**
- **Best improvement: +10.74%** (on `cadss` trace)
- **Worst case: -12.93%** (on some `fluid-test` configurations)

### Performance by Trace

| Trace | Perceptron Win Rate | Avg Accuracy Improvement | Best Improvement |
|-------|---------------------|--------------------------|------------------|
| **black-test** | 84.6% (33/39) | +2.88% | +8.03% |
| **cadss** | 89.7% (35/39) | +3.87% | +10.74% |
| **fluid-test** | 20.5% (8/39) | -3.71% | +2.87% |
| **ls** | 71.8% (28/39) | +1.16% | +7.35% |

**Insight:** Perceptron predictors excel on `black-test`, `cadss`, and `ls` traces but struggle with `fluid-test`.

---

## Best Configurations Per Trace

### black-test
- **Winner:** Perceptron-Std
- **Config:** s=7, b=24, g=0
- **Accuracy:** 82.94%
- **Storage:** 33,816 bits

### cadss
- **Winner:** Perceptron-Std
- **Config:** s=7, b=20, g=0
- **Accuracy:** 79.51%
- **Storage:** 29,716 bits

### fluid-test
- **Winner:** GSelect (Classic!)
- **Config:** s=9, b=4, g=2
- **Accuracy:** 94.14%
- **Storage:** 33,796 bits

### ls
- **Winner:** 2-bit (Classic!)
- **Config:** s=9, b=0, g=0
- **Accuracy:** 85.54%
- **Storage:** 33,792 bits

---

## Key Insights

### 1. Perceptron Advantages
- **Better with longer histories:** Perceptrons can effectively use b=20-24, much longer than classic predictors (b=2-8)
- **Superior on complex patterns:** Largest wins on `cadss` (+10.74%) and `black-test` (+8.03%)
- **Standard indexing (g=0) works best:** Perceptron-Std outperformed Perceptron-GShare and Perceptron-GSelect

### 2. Classic Predictor Advantages
- **Better on simple patterns:** Classic predictors won on `fluid-test` (high baseline accuracy ~94%)
- **More storage efficient for small budgets:** 2-bit counters use only 2 bits vs 8-bit perceptron weights
- **GSelect is competitive:** GSelect often matches or beats perceptrons on some traces

### 3. Storage Efficiency Trade-offs
- **Similar storage budgets:** Matched pairs typically within ±1% storage difference
- **Perceptron needs more bits for weights:** 8 bits/weight vs 2 bits/counter
- **Perceptron compensates with longer history:** Uses b=20-24 vs classic b=2-8

---

## Generated Visualizations

All figures saved in `experiments_final/results/figures/`:

1. **matched_pairs_accuracy.png** - Direct accuracy comparison for storage-matched configs
2. **accuracy_vs_storage.png** - Performance vs storage budget tradeoff curves
3. **misprediction_rate_comparison.png** - Distribution of misprediction rates by predictor type
4. **perceptron_history_length_impact.png** - Effect of history length (b) on perceptron accuracy
5. **best_configurations.png** - Summary table of best configs per trace

---

## Experiment Statistics

- **Total experiments run:** 612
- **Matched pairs:** 39 configuration pairs × 4 traces = 156 comparisons
- **Perceptron exploration:** 75 additional perceptron configs × 4 traces = 300 tests
- **Classic configs:** 39 configs × 4 traces = 156 tests
- **Traces tested:** black-test, cadss, fluid-test, ls
- **Predictor types:** 6 (2-bit, GShare, GSelect, Perceptron-Std, Perceptron-GShare, Perceptron-GSelect)

---

## Storage Budget Calculations

### Classic Predictors
```
Total bits = (2^s × 2 bits) + (2^s × 64 bits for BTB) + b bits (BHR)
           = 2^s × 66 bits + b
```

### Perceptron Predictors
```
Total bits = (2^s × (b+1) × 8 bits) + (2^s × 64 bits for BTB) + b bits (BHR)
           = 2^s × (8b + 8 + 64) + b
           = 2^s × (8b + 72) + b
```

**Example:** Classic with s=7, b=0 uses 8,448 bits. Matched perceptron with s=5, b=24 uses 8,472 bits (~0.3% difference).

---

## Conclusions

1. **Perceptron predictors are superior for most real-world traces** - winning 67% of matched comparisons

2. **History length matters** - Perceptrons benefit significantly from longer branch histories (b=20-24)

3. **Indexing scheme impact is trace-dependent** - Standard indexing (g=0) worked best overall, but GShare/GSelect can help on specific traces

4. **Not a silver bullet** - Classic predictors (especially GSelect) remain competitive on traces with simple, predictable branch patterns

5. **Storage efficiency** - While perceptrons need more bits per weight, they compensate by leveraging longer histories for better accuracy

---

## Files Generated

- `experiments_final/perceptron_comparison.py` - Experiment script
- `experiments_final/analyze_comparison.py` - Analysis script
- `experiments_final/results/perceptron_comparison_results.csv` - Raw data (612 experiments)
- `experiments_final/results/comparison_report.txt` - Text summary
- `experiments_final/results/figures/*.png` - 5 visualization plots
- `experiments_final/README.md` - Documentation

---

## Next Steps

To view the visualizations:
```bash
# Windows
explorer experiments_final\results\figures

# WSL/Linux
cd experiments_final/results/figures
ls -la
```

To re-run experiments:
```bash
wsl bash -c "cd /mnt/d/CodeRepos/15346/cadss-public-f25-cadss-eric-mohamed && python3 experiments_final/perceptron_comparison.py"
```

To re-analyze:
```bash
wsl bash -c "cd /mnt/d/CodeRepos/15346/cadss-public-f25-cadss-eric-mohamed && python3 experiments_final/analyze_comparison.py"
```
