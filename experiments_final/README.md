# Perceptron vs Classic Branch Predictor Comparison Experiments

This experiment suite compares the new **Perceptron-based branch predictor** (`final-project/`) with the classic predictors (`my-branch/`): 2-bit counters, GShare, and GSelect.

## Key Features

### Fair Comparison
- **Storage budget matching**: Configurations are paired to use similar amounts of storage (bits)
- Classic predictors: `2^s` counters × 2 bits/counter + BTB storage
- Perceptron predictors: `2^s` perceptrons × `(b+1)` weights × 8 bits/weight + BTB storage

### Configurations Tested

**Classic Predictors (`my-branch/`):**
- 2-bit counters (g=0): Various sizes (s=4 to s=10)
- GShare (g=1): Various sizes and BHR lengths
- GSelect (g=2): Various sizes and BHR lengths

**Perceptron Predictors (`final-project/`):**
- Standard indexing (g=0)
- GShare-style indexing (g=1)  
- GSelect-style indexing (g=2)
- Longer history lengths (b up to 20+)

### Traces
All experiments run on 4 real traces:
- `black-test.trace`
- `cadss.trace`
- `fluid-test.trace`
- `ls.trace`

## Usage

### 1. Build the project
```bash
make
```

### 2. Run experiments
```bash
# On Windows
python experiments_final\perceptron_comparison.py

# On Linux/WSL
python3 experiments_final/perceptron_comparison.py
```

This will:
- Generate ~100+ configuration pairs with matched storage budgets
- Run each configuration on all traces
- Save results to `experiments_final/results/perceptron_comparison_results.csv`

**Expected runtime:** 10-30 minutes depending on system

### 3. Analyze results
```bash
# On Windows
python experiments_final\analyze_comparison.py

# On Linux/WSL
python3 experiments_final/analyze_comparison.py
```

This will:
- Compute matched pair statistics
- Analyze performance by predictor type
- Generate visualizations
- Create a summary report

## Output Files

### `results/perceptron_comparison_results.csv`
Raw experimental data with columns:
- Configuration parameters (s, b, g)
- Storage bits used
- Performance metrics (accuracy, misprediction rate, ticks)
- Matched pair IDs for comparison

### `results/comparison_report.txt`
Text summary including:
- Overall statistics
- Best improvements per trace
- Best configurations per trace

### `results/figures/`
Generated visualizations:
- `matched_pairs_accuracy.png` - Direct accuracy comparison for matched storage budgets
- `accuracy_vs_storage.png` - Performance vs storage tradeoff curves
- `misprediction_rate_comparison.png` - Distribution of misprediction rates
- `perceptron_history_length_impact.png` - Effect of history length (b) on accuracy
- `best_configurations.png` - Summary table of best configs

## Key Questions Answered

1. **Does perceptron beat classic predictors with same storage?**
   - See matched pair analysis in report

2. **What's the optimal history length for perceptrons?**
   - See `perceptron_history_length_impact.png`

3. **Which indexing scheme works best?**
   - Compare Standard vs GShare vs GSelect in analysis

4. **Storage efficiency?**
   - See `accuracy_vs_storage.png` for efficiency curves

## Requirements

- Python 3.6+
- pandas
- matplotlib
- seaborn
- numpy

Install dependencies:
```bash
pip install pandas matplotlib seaborn numpy
```
