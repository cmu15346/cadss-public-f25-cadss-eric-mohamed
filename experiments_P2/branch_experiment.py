#!/usr/bin/env python3
"""
Branch Predictor Configuration Experiment Script

This script runs branch predictor simulations with different configurations
to analyze the impact of various design parameters within a 512 counter budget.
"""

import subprocess
import csv
import os
import math
import itertools
from pathlib import Path

def calculate_predictor_counters(s, b, g):
    """
    Calculate total number of counters needed for the predictor.
    
    Args:
        s: log2 of predictor size (number of counters = 2^s)
        b: BHR size in bits
        g: predictor model (0=2-bit, 1=GSHARE, 2=GSELECT, 3=Yeh-Patt)
    
    Returns:
        Total number of counters needed
    """
    num_counters = 2 ** s
    
    # For GSELECT, BHR size affects the effective predictor size
    if g == 2:  # GSELECT
        # GSELECT concatenates PC bits with BHR, so effective size depends on both
        # If b >= s, we fall back to basic indexing, but this shouldn't happen
        if b < s:
            # We still use 2^s counters, but organization is different
            pass
    
    return num_counters

def generate_configurations(max_counters=512):
    """
    Generate specific branch predictor configurations for focused comparisons:
    1. 2-bit predictors with various sizes
    2. GSELECT predictors with various sizes and BHR sizes
    
    Returns:
        List of configuration dictionaries
    """
    configurations = []
    
    # Configuration 1: 2-bit predictors with different sizes
    print("Generating 2-bit predictor configurations...")
    for s in range(0, 10):  # s=0 to s=9 (1 to 512 counters)
        counters_needed = 2 ** s
        if counters_needed <= max_counters:
            configurations.append({
                'type': '2-bit',
                's': s,
                'b': 0,  # No BHR for 2-bit
                'g': 0,
                'counters': counters_needed,
                'predictor_size': counters_needed,
                'bhr_size': 0
            })
    
    # Configuration 2: GSELECT predictors with varying sizes and BHR sizes
    print("Generating GSELECT predictor configurations...")
    for s in range(1, 10):  # Predictor sizes
        for b in range(1, min(s, 8)):  # BHR sizes (must be < s, limit to reasonable range)
            counters_needed = 2 ** s
            if counters_needed <= max_counters:
                configurations.append({
                    'type': 'GSELECT',
                    's': s,
                    'b': b,
                    'g': 2,
                    'counters': counters_needed,
                    'predictor_size': counters_needed,
                    'bhr_size': b
                })
    
    print(f"Generated {len(configurations)} configurations for focused comparison")
    return configurations

def create_config_file(config, config_path):
    """Create a configuration file for the branch predictor simulator."""
    with open(config_path, 'w') as f:
        f.write("__processor -p 1 // __other\n")
        f.write("__cache -E 1 -b 4 -s 8\n")  # Basic cache config
        f.write("// the name is \"foo/*\" and it takes three arguments\n")
        f.write("__foo/* -a 1 */\n")
        
        # Build branch predictor arguments
        branch_args = f"__branch -s {config['s']} -b {config['b']} -g {config['g']}"
        f.write(branch_args + "\n")

def parse_simulator_output(output):
    """
    Parse the simulator output to extract performance metrics.
    
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {
        'ticks': 0,
        'branches': 0,
        'mispredictions': 0,
        'accuracy': 0.0
    }
    
    lines = output.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Look for the main "Ticks" metric
        if line.startswith('Ticks - '):
            try:
                metrics['ticks'] = int(line.split('- ')[1])
            except:
                pass
    
    return metrics

def count_branch_instructions(trace_file):
    """
    Count the total number of branch instructions in a trace file.
    Branch instructions start with 'B'.
    
    Returns:
        Number of branch instructions in the trace file
    """
    try:
        with open(trace_file, 'r') as f:
            return sum(1 for line in f if line.strip().startswith('B'))
    except Exception as e:
        print(f"Error counting branches in {trace_file}: {e}")
        return 0

def count_total_lines(trace_file):
    """
    Count the total number of lines in a trace file for AAT calculation.
    
    Returns:
        Total number of lines in the trace file
    """
    try:
        with open(trace_file, 'r') as f:
            return sum(1 for line in f if line.strip())
    except Exception as e:
        print(f"Error counting lines in {trace_file}: {e}")
        return 0

def run_simulation(config_file, trace_file):
    """
    Run the branch predictor simulator and parse the output.
    
    Returns:
        Dictionary with simulation results or None if failed
    """
    try:
        # Use the correct command format for branch prediction
        if os.name == 'nt':
            cmd = ["./cadss-engine.exe", "-s", config_file, "-t", trace_file, "-b", "my-branch"]
        else:
            cmd = ["./cadss-engine", "-s", config_file, "-t", trace_file, "-b", "my-branch"]
            
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"Simulation failed for {config_file} with {trace_file}")
            print(f"Error: {result.stderr}")
            return None
        
        # Parse the output to extract metrics
        output = result.stdout
        metrics = parse_simulator_output(output)
        
        # Count total branch instructions and total lines from trace file
        total_branches = count_branch_instructions(trace_file)
        total_lines = count_total_lines(trace_file)
        
        # Calculate AAT (Average Access Time)
        aat = metrics['ticks'] / total_lines if total_lines > 0 else 0
        
        return {
            'success': True,
            'raw_output': output,
            'ticks': metrics['ticks'],
            'total_branches': total_branches,
            'total_lines': total_lines,
            'aat': aat
        }
        
    except subprocess.TimeoutExpired:
        print(f"Simulation timed out for {config_file} with {trace_file}")
        return None
    except Exception as e:
        print(f"Error running simulation: {e}")
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
    
    # Get list of trace files suitable for branch prediction
    trace_candidates = [
        Path("traces/branch/black-test.trace"),
        Path("traces/branch/cadss.trace"),
        Path("traces/branch/fluid-test.trace"),
        Path("traces/branch/ls.trace")
    ]
    
    
    # Filter to traces that exist and likely contain branch instructions
    trace_files = []
    for trace in trace_candidates:
        if trace.exists():
            trace_files.append(trace)
    
    if not trace_files:
        print("Error: No suitable trace files found")
        return
    
    print(f"Found {len(trace_files)} trace files:")
    for trace in trace_files:
        branches = count_branch_instructions(trace)
        print(f"  {trace.name}: {branches} branch instructions")
    
    # Generate configurations
    print("\nGenerating branch predictor configurations...")
    configurations = generate_configurations()
    
    # Show configuration type distribution
    config_types = {}
    for config in configurations:
        config_type = config['type']
        config_types[config_type] = config_types.get(config_type, 0) + 1
    
    print("\nConfiguration breakdown:")
    for config_type, count in config_types.items():
        print(f"  {config_type}: {count} configurations")
    
    counter_usage = [c['counters'] for c in configurations]
    print(f"\nCounter usage range: {min(counter_usage)} - {max(counter_usage)} counters")
    print(f"Average usage: {sum(counter_usage)/len(counter_usage):.1f} counters")
    
    # Create results directory
    results_dir = Path("experiment_results")
    results_dir.mkdir(exist_ok=True)
    
    # Prepare CSV output
    csv_file = results_dir / "branch_experiment_results.csv"
    fieldnames = ['config_id', 'trace', 'type', 's', 'b', 'g', 'counters', 'predictor_size', 'bhr_size',
                  'simulation_success', 'total_branches', 'total_lines', 'ticks', 'aat', 'raw_output']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        config_id = 0
        for config in configurations:
            config_id += 1
            
            # Create temporary config file
            temp_config = results_dir / f"temp_branch_config_{config_id}.config"
            create_config_file(config, temp_config)
            
            print(f"Testing configuration {config_id}/{len(configurations)}: "
                  f"{config['type']} s={config['s']} b={config['b']} g={config['g']} "
                  f"counters={config['counters']}")
            
            for trace_file in trace_files:
                trace_name = trace_file.stem
                
                # Skip traces with no branch instructions
                if count_branch_instructions(trace_file) == 0:
                    continue
                
                # Run simulation
                result = run_simulation(str(temp_config), str(trace_file))
                
                # Write results
                row = {
                    'config_id': config_id,
                    'trace': trace_name,
                    'type': config['type'],
                    's': config['s'],
                    'b': config['b'],
                    'g': config['g'],
                    'counters': config['counters'],
                    'predictor_size': config['predictor_size'],
                    'bhr_size': config['bhr_size'],
                    'simulation_success': result is not None and result.get('success', False),
                    'total_branches': result.get('total_branches', 0) if result else 0,
                    'total_lines': result.get('total_lines', 0) if result else 0,
                    'ticks': result.get('ticks', 0) if result else 0,
                    'aat': result.get('aat', 0.0) if result else 0.0,
                    'raw_output': result.get('raw_output', '') if result else ''
                }
                
                writer.writerow(row)
            
            # Clean up temp config file
            if temp_config.exists():
                temp_config.unlink()
            
            # Optional: limit for testing (remove for full experiment)
            # if config_id >= 20:
            #     print("Limiting to first 20 configurations for testing")
            #     break
    
    print(f"Experiment completed. Results saved to {csv_file}")
    print(f"Tested {min(config_id, len(configurations))} configurations "
          f"across {len([t for t in trace_files if count_branch_instructions(t) > 0])} trace files")
    print("Focused comparisons:")
    print("  - 2-bit predictors with various sizes")
    print("  - GSELECT predictors with various sizes and BHR configurations")
    print("  - AAT (Average Access Time) calculated as ticks/total_trace_lines")

if __name__ == "__main__":
    main()