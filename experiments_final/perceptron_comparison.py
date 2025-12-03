#!/usr/bin/env python3
"""
Perceptron vs Classic Branch Predictor Comparison Experiment

This script compares the new perceptron-based predictor with classic predictors
(2-bit, GShare, GSelect) under fair storage budget constraints.

Storage Budget Calculations:
- Classic predictors: 2^s counters × 2 bits/counter = 2^(s+1) bits
- Perceptron predictor: 2^s perceptrons × (b+1) weights × 8 bits/weight = 2^s × (b+1) × 8 bits
  (assuming 8-bit weights for reasonable dynamic range)
"""

import subprocess
import csv
import os
import math
from pathlib import Path


def calculate_classic_storage_bits(s, b, g):
    """
    Calculate storage bits for classic predictors (2-bit, GShare, GSelect).
    
    Args:
        s: log2 of predictor size
        b: BHR size (used by GShare/GSelect)
        g: predictor model (0=2-bit, 1=GShare, 2=GSelect)
    
    Returns:
        Total bits of storage
    """
    num_counters = 2 ** s
    bits_per_counter = 2  # 2-bit saturating counters
    
    # BTB storage (assume same size as counter array, storing 64-bit addresses)
    btb_bits = num_counters * 64
    
    # Counter storage
    counter_bits = num_counters * bits_per_counter
    
    # BHR storage (global, only one register)
    bhr_bits = b if b > 0 else 0
    
    total_bits = counter_bits + btb_bits + bhr_bits
    return total_bits


def calculate_perceptron_storage_bits(s, b, g):
    """
    Calculate storage bits for perceptron predictor.
    
    Args:
        s: log2 of number of perceptrons
        b: history length (determines weights per perceptron)
        g: indexing model (0=standard, 1=gshare, 2=gselect)
    
    Returns:
        Total bits of storage
    """
    num_perceptrons = 2 ** s
    weights_per_perceptron = b + 1  # b history weights + 1 bias
    bits_per_weight = 8  # Assume 8-bit signed integers for weights
    
    # BTB storage (same as classic)
    btb_bits = num_perceptrons * 64
    
    # Weight table storage
    weight_bits = num_perceptrons * weights_per_perceptron * bits_per_weight
    
    # BHR storage (global)
    bhr_bits = b if b > 0 else 0
    
    total_bits = weight_bits + btb_bits + bhr_bits
    return total_bits


def generate_matched_configurations(max_storage_bits=50000):
    """
    Generate predictor configurations with matched storage budgets.
    
    For each classic predictor configuration, find perceptron configurations
    with similar storage requirements.
    
    Returns:
        List of configuration pairs for comparison
    """
    configurations = []
    
    # Generate classic predictor configurations
    print("Generating classic predictor configurations...")
    
    classic_configs = []
    
    # 2-bit predictor with various sizes
    for s in range(4, 11):  # s=4 to s=10 (16 to 1024 counters)
        storage = calculate_classic_storage_bits(s, 0, 0)
        if storage <= max_storage_bits:
            classic_configs.append({
                'type': '2-bit',
                's': s,
                'b': 0,
                'g': 0,
                'storage_bits': storage,
                'predictor_path': 'my-branch/'
            })
    
    # GShare predictor with various sizes and BHR sizes
    for s in range(4, 11):
        for b in range(2, min(s+1, 10), 2):  # b=2,4,6,8...
            storage = calculate_classic_storage_bits(s, b, 1)
            if storage <= max_storage_bits:
                classic_configs.append({
                    'type': 'GShare',
                    's': s,
                    'b': b,
                    'g': 1,
                    'storage_bits': storage,
                    'predictor_path': 'my-branch/'
                })
    
    # GSelect predictor with various sizes and BHR sizes
    for s in range(4, 11):
        for b in range(2, min(s, 10), 2):  # b must be < s
            storage = calculate_classic_storage_bits(s, b, 2)
            if storage <= max_storage_bits:
                classic_configs.append({
                    'type': 'GSelect',
                    's': s,
                    'b': b,
                    'g': 2,
                    'storage_bits': storage,
                    'predictor_path': 'my-branch/'
                })
    
    print(f"Generated {len(classic_configs)} classic configurations")
    
    # For each classic config, find matching perceptron configs
    print("\nGenerating matched perceptron configurations...")
    
    for classic in classic_configs:
        target_storage = classic['storage_bits']
        
        # Try different perceptron configurations to match storage
        # Since perceptron uses 8 bits per weight, we need smaller s or b
        best_match = None
        best_diff = float('inf')
        
        for perc_s in range(2, 10):
            for perc_b in range(2, 25):  # Perceptrons can use longer history
                for perc_g in [0, 1, 2]:  # Try all indexing schemes
                    perc_storage = calculate_perceptron_storage_bits(perc_s, perc_b, perc_g)
                    
                    # Find closest match
                    diff = abs(perc_storage - target_storage)
                    if diff < best_diff and perc_storage <= max_storage_bits:
                        best_diff = diff
                        best_match = {
                            'type': f'Perceptron-{["Std", "GShare", "GSelect"][perc_g]}',
                            's': perc_s,
                            'b': perc_b,
                            'g': perc_g,
                            'storage_bits': perc_storage,
                            'predictor_path': 'final-project/'
                        }
        
        if best_match and best_diff / target_storage < 0.2:  # Within 20% match
            configurations.append({
                'classic': classic,
                'perceptron': best_match,
                'storage_diff_pct': (best_match['storage_bits'] - classic['storage_bits']) / classic['storage_bits'] * 100
            })
    
    print(f"Generated {len(configurations)} matched configuration pairs")
    
    # Also add some perceptron-only configurations for exploration
    print("\nAdding perceptron exploration configurations...")
    perc_exploration = []
    for s in range(3, 8):
        for b in [4, 8, 12, 16, 20]:
            for g in [0, 1, 2]:
                storage = calculate_perceptron_storage_bits(s, b, g)
                if storage <= max_storage_bits:
                    perc_exploration.append({
                        'type': f'Perceptron-{["Std", "GShare", "GSelect"][g]}',
                        's': s,
                        'b': b,
                        'g': g,
                        'storage_bits': storage,
                        'predictor_path': 'final-project/'
                    })
    
    print(f"Generated {len(perc_exploration)} exploration configurations")
    
    return configurations, classic_configs, perc_exploration


def create_config_file(config, config_path):
    """Create a configuration file for the simulator."""
    with open(config_path, 'w') as f:
        f.write("__processor -p 1 // __other\n")
        f.write("__cache -E 2 -b 6 -s 8\n")  # Reasonable fixed cache config
        f.write("// the name is \"foo/*\" and it takes three arguments\n")
        f.write("__foo/* -a 1 */\n")
        
        # Build branch predictor arguments
        branch_args = f"__branch -s {config['s']} -b {config['b']} -g {config['g']}"
        f.write(branch_args + "\n")


def parse_simulator_output(output):
    """
    Parse simulator output to extract metrics.
    
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {
        'ticks': 0,
        'total_branches': 0,
        'correct_predictions': 0,
        'mispredictions': 0,
        'accuracy': 0.0,
        'misprediction_rate': 0.0
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Extract ticks
        if line.startswith('Ticks - '):
            try:
                metrics['ticks'] = int(line.split('- ')[1])
            except:
                pass
        
        # Extract branch statistics
        if 'Total Branches' in line and ':' in line:
            try:
                metrics['total_branches'] = int(line.split(':')[1].strip())
            except:
                pass
        
        if 'Correct Predictions' in line and ':' in line:
            try:
                metrics['correct_predictions'] = int(line.split(':')[1].strip())
            except:
                pass
        
        if 'Mispredictions' in line and ':' in line:
            try:
                metrics['mispredictions'] = int(line.split(':')[1].strip())
            except:
                pass
        
        if 'Accuracy' in line and ':' in line and '%' in line:
            try:
                metrics['accuracy'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
        
        if 'Misprediction Rate' in line and ':' in line and '%' in line:
            try:
                metrics['misprediction_rate'] = float(line.split(':')[1].strip().replace('%', ''))
            except:
                pass
    
    return metrics


def run_simulation(config_file, trace_file, predictor_path):
    """
    Run the simulator and parse output.
    
    Args:
        config_file: Path to config file
        trace_file: Path to trace file
        predictor_path: Path to predictor implementation (my-branch/ or final-project/)
    
    Returns:
        Dictionary with simulation results or None if failed
    """
    try:
        if os.name == 'nt':
            cmd = ["./cadss-engine.exe", "-s", config_file, "-t", trace_file, "-b", predictor_path]
        else:
            cmd = ["./cadss-engine", "-s", config_file, "-t", trace_file, "-b", predictor_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Parse output even if return code is not 0 (there might be warnings)
        output = result.stdout
        metrics = parse_simulator_output(output)
        
        return {
            'success': metrics['ticks'] > 0,
            'raw_output': output,
            **metrics
        }
        
    except subprocess.TimeoutExpired:
        print(f"  Simulation timed out")
        return None
    except Exception as e:
        print(f"  Error running simulation: {e}")
        return None


def main():
    """Main experiment runner."""
    # Check if simulator exists
    simulator_names = ["./cadss-engine", "./cadss-engine.exe"]
    simulator_path = None
    
    for name in simulator_names:
        if os.path.exists(name):
            simulator_path = name
            break
    
    if not simulator_path:
        print("Error: cadss-engine not found. Please build the project first.")
        return
    
    # Get trace files (excluding test.trace)
    trace_dir = Path("traces/branch")
    trace_files = [
        trace_dir / "black-test.trace",
        trace_dir / "cadss.trace",
        trace_dir / "fluid-test.trace",
        trace_dir / "ls.trace"
    ]
    
    trace_files = [t for t in trace_files if t.exists()]
    
    if not trace_files:
        print("Error: No trace files found")
        return
    
    print(f"Found {len(trace_files)} trace files:")
    for trace in trace_files:
        print(f"  {trace.name}")
    
    # Generate configurations
    print("\n" + "="*60)
    print("GENERATING CONFIGURATIONS")
    print("="*60)
    
    matched_pairs, classic_configs, perc_exploration = generate_matched_configurations()
    
    # Create results directory
    results_dir = Path("experiments_final/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare CSV output
    csv_file = results_dir / "perceptron_comparison_results.csv"
    fieldnames = [
        'experiment_type', 'config_id', 'trace', 'predictor_type', 'predictor_path',
        's', 'b', 'g', 'storage_bits',
        'simulation_success', 'ticks', 'total_branches', 'correct_predictions',
        'mispredictions', 'accuracy', 'misprediction_rate',
        'matched_classic_id', 'matched_perc_id', 'storage_diff_pct',
        'raw_output'
    ]
    
    print("\n" + "="*60)
    print("RUNNING EXPERIMENTS")
    print("="*60)
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        experiment_num = 0
        
        # Run matched pair experiments
        print("\n--- MATCHED PAIR COMPARISONS ---")
        for pair_id, pair in enumerate(matched_pairs, 1):
            classic = pair['classic']
            perceptron = pair['perceptron']
            
            print(f"\nPair {pair_id}/{len(matched_pairs)}:")
            print(f"  Classic: {classic['type']} (s={classic['s']}, b={classic['b']}, g={classic['g']}) - {classic['storage_bits']} bits")
            print(f"  Perceptron: {perceptron['type']} (s={perceptron['s']}, b={perceptron['b']}, g={perceptron['g']}) - {perceptron['storage_bits']} bits")
            print(f"  Storage diff: {pair['storage_diff_pct']:.1f}%")
            
            for trace_file in trace_files:
                trace_name = trace_file.stem
                
                # Test classic predictor
                temp_config = results_dir / f"temp_config_{pair_id}_classic.config"
                create_config_file(classic, temp_config)
                
                print(f"    Testing {classic['type']} on {trace_name}...", end='')
                classic_result = run_simulation(str(temp_config), str(trace_file), classic['predictor_path'])
                print(f" {'✓' if classic_result and classic_result['success'] else '✗'}")
                
                experiment_num += 1
                if classic_result:
                    writer.writerow({
                        'experiment_type': 'matched_pair',
                        'config_id': experiment_num,
                        'trace': trace_name,
                        'predictor_type': classic['type'],
                        'predictor_path': classic['predictor_path'],
                        's': classic['s'],
                        'b': classic['b'],
                        'g': classic['g'],
                        'storage_bits': classic['storage_bits'],
                        'simulation_success': classic_result['success'],
                        'ticks': classic_result.get('ticks', 0),
                        'total_branches': classic_result.get('total_branches', 0),
                        'correct_predictions': classic_result.get('correct_predictions', 0),
                        'mispredictions': classic_result.get('mispredictions', 0),
                        'accuracy': classic_result.get('accuracy', 0.0),
                        'misprediction_rate': classic_result.get('misprediction_rate', 0.0),
                        'matched_classic_id': experiment_num,
                        'matched_perc_id': experiment_num + 1,
                        'storage_diff_pct': pair['storage_diff_pct'],
                        'raw_output': classic_result.get('raw_output', '')
                    })
                
                temp_config.unlink(missing_ok=True)
                
                # Test perceptron predictor
                temp_config = results_dir / f"temp_config_{pair_id}_perc.config"
                create_config_file(perceptron, temp_config)
                
                print(f"    Testing {perceptron['type']} on {trace_name}...", end='')
                perc_result = run_simulation(str(temp_config), str(trace_file), perceptron['predictor_path'])
                print(f" {'✓' if perc_result and perc_result['success'] else '✗'}")
                
                experiment_num += 1
                if perc_result:
                    writer.writerow({
                        'experiment_type': 'matched_pair',
                        'config_id': experiment_num,
                        'trace': trace_name,
                        'predictor_type': perceptron['type'],
                        'predictor_path': perceptron['predictor_path'],
                        's': perceptron['s'],
                        'b': perceptron['b'],
                        'g': perceptron['g'],
                        'storage_bits': perceptron['storage_bits'],
                        'simulation_success': perc_result['success'],
                        'ticks': perc_result.get('ticks', 0),
                        'total_branches': perc_result.get('total_branches', 0),
                        'correct_predictions': perc_result.get('correct_predictions', 0),
                        'mispredictions': perc_result.get('mispredictions', 0),
                        'accuracy': perc_result.get('accuracy', 0.0),
                        'misprediction_rate': perc_result.get('misprediction_rate', 0.0),
                        'matched_classic_id': experiment_num - 1,
                        'matched_perc_id': experiment_num,
                        'storage_diff_pct': pair['storage_diff_pct'],
                        'raw_output': perc_result.get('raw_output', '')
                    })
                
                temp_config.unlink(missing_ok=True)
        
        # Run perceptron exploration experiments
        print("\n--- PERCEPTRON EXPLORATION ---")
        for perc_id, perc in enumerate(perc_exploration, 1):
            if perc_id % 10 == 1:
                print(f"\nPerceptron config {perc_id}/{len(perc_exploration)}: {perc['type']} (s={perc['s']}, b={perc['b']}, g={perc['g']}) - {perc['storage_bits']} bits")
            
            for trace_file in trace_files:
                trace_name = trace_file.stem
                
                temp_config = results_dir / f"temp_config_explore_{perc_id}.config"
                create_config_file(perc, temp_config)
                
                perc_result = run_simulation(str(temp_config), str(trace_file), perc['predictor_path'])
                
                experiment_num += 1
                if perc_result:
                    writer.writerow({
                        'experiment_type': 'perceptron_exploration',
                        'config_id': experiment_num,
                        'trace': trace_name,
                        'predictor_type': perc['type'],
                        'predictor_path': perc['predictor_path'],
                        's': perc['s'],
                        'b': perc['b'],
                        'g': perc['g'],
                        'storage_bits': perc['storage_bits'],
                        'simulation_success': perc_result['success'],
                        'ticks': perc_result.get('ticks', 0),
                        'total_branches': perc_result.get('total_branches', 0),
                        'correct_predictions': perc_result.get('correct_predictions', 0),
                        'mispredictions': perc_result.get('mispredictions', 0),
                        'accuracy': perc_result.get('accuracy', 0.0),
                        'misprediction_rate': perc_result.get('misprediction_rate', 0.0),
                        'matched_classic_id': '',
                        'matched_perc_id': '',
                        'storage_diff_pct': '',
                        'raw_output': perc_result.get('raw_output', '')
                    })
                
                temp_config.unlink(missing_ok=True)
    
    print("\n" + "="*60)
    print("EXPERIMENT COMPLETE")
    print("="*60)
    print(f"Results saved to: {csv_file}")
    print(f"Total experiments run: {experiment_num}")
    print(f"Matched pairs tested: {len(matched_pairs)}")
    print(f"Perceptron exploration configs: {len(perc_exploration)}")


if __name__ == "__main__":
    main()
