# P3 Integration Experiments - Quick Start (Windows)

## Running in WSL (Recommended)

The simulator is built for Linux, so use WSL to run experiments:

### 1. Preview configurations
```powershell
wsl bash experiments_P3/run_experiments.sh preview
```

### 2. Test single configuration
```powershell
wsl bash experiments_P3/run_experiments.sh test
```

### 3. Run full experiments
```powershell
wsl bash experiments_P3/run_experiments.sh run
```

### 4. Analyze results
```powershell
wsl bash experiments_P3/run_experiments.sh analyze
```

## Alternative: Direct Python Commands in WSL

```bash
# In WSL
cd /mnt/d/CodeRepos/15346/cadss-public-f25-cadss-eric-mohamed

# Preview
python3 experiments_P3/preview_configs.py

# Test
python3 experiments_P3/test_single.py

# Run experiments
python3 experiments_P3/integration_experiment.py

# Analyze
python3 experiments_P3/analyze_results.py
```

## What Gets Generated

After running experiments:
- `experiments_P3/experiment_results/integration_results.csv` - Raw data
- `experiments_P3/experiment_results/figures/*.png` - Plots (if matplotlib installed)

## Time Estimate

- **Preview**: < 1 second
- **Test single**: ~5 seconds
- **Full experiments**: ~2-3 hours (1,680 simulations)
- **Analysis**: ~10 seconds

## Troubleshooting

### "Command not found: python3"
Install Python in WSL:
```bash
sudo apt update
sudo apt install python3 python3-pip
```

### "No module named 'pandas'" (for analysis)
Install required packages in WSL:
```bash
pip3 install pandas numpy matplotlib seaborn
```

### Experiments taking too long
You can reduce the number of configurations by editing:
- `experiments_P3/integration_experiment.py`
- Modify the `generate_*_configs()` functions to return fewer configs

## Quick Test Before Full Run

Always test first to make sure everything works:
```powershell
wsl bash experiments_P3/run_experiments.sh test
```

If that succeeds, you're ready for the full experiment!
