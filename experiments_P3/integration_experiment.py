#!/usr/bin/env python3
"""
P3 Integration Experiment Script

This script explores the integration of cache and branch predictor simulators
in the superscalar processor. It tests various combinations of:
1. Cache configurations (from P1)
2. Branch predictor configurations (from P2)
3. Processor pipeline configurations (fetch rate, FUs, dispatch, etc.)

The goal is to understand how these components interact and affect overall
performance in terms of total execution time (ticks) and AAT.
"""

import subprocess
import csv
import os
import math
import itertools
from pathlib import Path

def calculate_cache_size(s, E, b, r=0, i=0, use_rrip=False):
    """
    Calculate total cache size in bytes (from P1).
    
    Args:
        s: set index bits (number of sets = 2^s)
        E: lines per set 
        b: block offset bits (block size = 2^b bytes)
        r: RRIP bits per line (if use_rrip=True)
        i: victim cache entries
        use_rrip: True for RRIP, False for LRU
    
    Returns:
        Total cache size in bytes
    """
    num_sets = 2 ** s
    block_size = 2 ** b
    
    # Data storage
    data_size = num_sets * E * block_size
    
    # Tag bits per line (assuming 64-bit addresses)
    tag_bits = 64 - s - b
    tag_storage_bits = num_sets * E * tag_bits
    
    # Valid bits
    valid_bits = num_sets * E * 1
    
    # Replacement policy bits
    if use_rrip:
        replacement_bits = num_sets * E * r
    else:
        # LRU needs log2(E) bits per line
        lru_bits = math.ceil(math.log2(E)) if E > 1 else 1
        replacement_bits = num_sets * E * lru_bits
    
    # Victim cache (if enabled)
    victim_bits = 0
    if i > 0:
        # Each victim entry needs tag + valid bit
        victim_tag_bits = 64 - b  # No set index for victim cache
        victim_bits = i * (victim_tag_bits + 1)
        # Victim LRU bits
        victim_lru_bits = math.ceil(math.log2(i)) if i > 1 else 1
        victim_bits += i * victim_lru_bits
    
    # Total overhead in bits
    overhead_bits = tag_storage_bits + valid_bits + replacement_bits + victim_bits
    overhead_bytes = math.ceil(overhead_bits / 8)
    
    total_size = data_size + overhead_bytes
    return total_size

def generate_cache_configs(max_size_bytes=54 * 1024):
    """
    Generate representative cache configurations for integration testing.
    Focus on diverse, high-performing configurations from P1.
    """
    configs = []
    
    # Configuration set 1: Small, fast caches (low latency)
    # Direct-mapped and low associativity - use smaller block sizes to fit budget
    configs.extend([
        {'type': 'Small-DM', 's': 8, 'E': 1, 'b': 6, 'r': 0, 'i': 0},    # 16KB direct-mapped
        {'type': 'Small-2way', 's': 7, 'E': 2, 'b': 6, 'r': 0, 'i': 0},  # 16KB 2-way
        {'type': 'Small-4way', 's': 6, 'E': 4, 'b': 6, 'r': 0, 'i': 0},  # 16KB 4-way
    ])
    
    # Configuration set 2: Medium-sized caches (balanced)
    configs.extend([
        {'type': 'Med-2way', 's': 8, 'E': 2, 'b': 6, 'r': 0, 'i': 0},    # 32KB 2-way
        {'type': 'Med-4way-LRU', 's': 7, 'E': 4, 'b': 6, 'r': 0, 'i': 0}, # 32KB 4-way
        {'type': 'Med-4way-RRIP', 's': 7, 'E': 4, 'b': 6, 'r': 3, 'i': 0}, # 32KB 4-way RRIP
    ])
    
    # Configuration set 3: Larger associativity
    configs.extend([
        {'type': 'Large-8way', 's': 6, 'E': 8, 'b': 6, 'r': 0, 'i': 0},  # 32KB 8-way
        {'type': 'Large-16way', 's': 5, 'E': 16, 'b': 6, 'r': 0, 'i': 0}, # 32KB 16-way
    ])
    
    # Configuration set 4: With victim cache (smaller main cache + victim)
    configs.extend([
        {'type': 'Victim-2way', 's': 6, 'E': 2, 'b': 6, 'r': 0, 'i': 4},  # 8KB 2-way + 4-entry victim
        {'type': 'Victim-4way', 's': 5, 'E': 4, 'b': 6, 'r': 0, 'i': 8},  # 8KB 4-way + 8-entry victim
    ])
    
    # Calculate sizes and filter
    valid_configs = []
    for config in configs:
        size = calculate_cache_size(
            config['s'], config['E'], config['b'], 
            config['r'], config['i'], 
            use_rrip=(config['r'] > 0)
        )
        if size <= max_size_bytes:
            config['size'] = size
            valid_configs.append(config)
    
    return valid_configs

def generate_branch_configs(max_counters=512):
    """
    Generate representative branch predictor configurations for integration testing.
    Focus on diverse configurations from P2.
    """
    configs = []
    
    # Configuration set 1: Small predictors
    configs.extend([
        {'type': '2bit-Small', 's': 5, 'b': 0, 'g': 0, 'counters': 32},      # 32 counters
        {'type': '2bit-Medium', 's': 7, 'b': 0, 'g': 0, 'counters': 128},    # 128 counters
        {'type': '2bit-Large', 's': 9, 'b': 0, 'g': 0, 'counters': 512},     # 512 counters
    ])
    
    # Configuration set 2: GSELECT with various BHR sizes
    configs.extend([
        {'type': 'GSELECT-2', 's': 7, 'b': 2, 'g': 2, 'counters': 128},      # 128 counters, 2-bit BHR
        {'type': 'GSELECT-4', 's': 8, 'b': 4, 'g': 2, 'counters': 256},      # 256 counters, 4-bit BHR
        {'type': 'GSELECT-6', 's': 9, 'b': 6, 'g': 2, 'counters': 512},      # 512 counters, 6-bit BHR
    ])
    
    # Configuration set 3: GSHARE (for comparison)
    configs.extend([
        {'type': 'GSHARE-Small', 's': 6, 'b': 4, 'g': 1, 'counters': 64},    # 64 counters, 4-bit BHR
        {'type': 'GSHARE-Large', 's': 8, 'b': 6, 'g': 1, 'counters': 256},   # 256 counters, 6-bit BHR
    ])
    
    return configs

def generate_processor_configs():
    """
    Generate processor pipeline configurations to explore.
    Focus on parameters that affect how well the processor hides stalls.
    """
    configs = []
    
    # Baseline: Minimal resources
    configs.append({
        'type': 'Baseline',
        'f': 1,  # fetch rate
        'd': 1,  # dispatch multiplier
        'm': 1,  # schedule multiplier (RS size = m * num_FUs)
        'j': 1,  # fast ALU FUs
        'k': 1,  # long ALU FUs
        'c': 1,  # CDBs
    })
    
    # Increased fetch width (helps with branch mispredictions)
    configs.append({
        'type': 'Wide-Fetch',
        'f': 4,
        'd': 1,
        'm': 1,
        'j': 1,
        'k': 1,
        'c': 1,
    })
    
    # More functional units (helps hide cache miss latency)
    configs.append({
        'type': 'More-FUs',
        'f': 2,
        'd': 1,
        'm': 2,
        'j': 4,  # 4 fast ALU FUs
        'k': 2,  # 2 long ALU FUs
        'c': 2,
    })
    
    # Larger reservation stations (more instructions in flight)
    configs.append({
        'type': 'Large-RS',
        'f': 2,
        'd': 2,
        'm': 4,  # 4x RS size per FU
        'j': 2,
        'k': 1,
        'c': 2,
    })
    
    # Aggressive dispatch (fill pipeline quickly)
    configs.append({
        'type': 'Aggressive-Dispatch',
        'f': 2,
        'd': 3,  # 3x dispatch rate
        'm': 2,
        'j': 2,
        'k': 1,
        'c': 2,
    })
    
    # Balanced superscalar (all parameters increased)
    configs.append({
        'type': 'Balanced',
        'f': 2,
        'd': 2,
        'm': 2,
        'j': 2,
        'k': 1,
        'c': 2,
    })
    
    # High-end superscalar
    configs.append({
        'type': 'High-End',
        'f': 4,
        'd': 2,
        'm': 3,
        'j': 4,
        'k': 2,
        'c': 4,
    })
    
    return configs

def create_config_file(proc_config, cache_config, branch_config, config_path):
    """Create a complete configuration file for the simulator."""
    with open(config_path, 'w') as f:
        # Processor configuration
        proc_args = (f"__processor -f {proc_config['f']} -d {proc_config['d']} "
                    f"-m {proc_config['m']} -j {proc_config['j']} "
                    f"-k {proc_config['k']} -c {proc_config['c']}")
        f.write(proc_args + "\n")
        
        # Cache configuration
        cache_args = f"__cache -E {cache_config['E']} -b {cache_config['b']} -s {cache_config['s']}"
        if cache_config['i'] > 0:
            cache_args += f" -i {cache_config['i']}"
        if cache_config['r'] > 0:
            cache_args += f" -R {cache_config['r']}"
        f.write(cache_args + "\n")
        
        # Branch predictor configuration
        branch_args = f"__branch -s {branch_config['s']} -b {branch_config['b']} -g {branch_config['g']}"
        f.write(branch_args + "\n")

def count_trace_instructions(trace_file):
    """
    Count the total number of instructions in a trace file.
    
    Returns:
        Number of instruction lines in the trace file
    """
    try:
        with open(trace_file, 'r') as f:
            return sum(1 for line in f if line.strip() and not line.startswith('//'))
    except Exception as e:
        print(f"Error counting instructions in {trace_file}: {e}")
        return 0

def count_instruction_types(trace_file):
    """
    Count different instruction types in the trace file.
    
    Returns:
        Dictionary with counts of each instruction type
    """
    counts = {'A': 0, 'L': 0, 'S': 0, 'B': 0, 'X': 0}
    try:
        with open(trace_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('//'):
                    op_type = line[0]
                    if op_type in counts:
                        counts[op_type] += 1
    except Exception as e:
        print(f"Error analyzing {trace_file}: {e}")
    
    return counts

def parse_simulator_output(output):
    """
    Parse the simulator output to extract performance metrics.
    
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {'ticks': 0}
    
    lines = output.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('Ticks - '):
            try:
                metrics['ticks'] = int(line.split('- ')[1])
            except:
                pass
    
    return metrics

def run_simulation(config_file, trace_file, timeout=300):
    """
    Run the integrated simulator and parse the output.
    
    Args:
        config_file: Path to configuration file
        trace_file: Path to trace file
        timeout: Timeout in seconds
    
    Returns:
        Dictionary with simulation results or None if failed
    """
    try:
        # Use my-processor with my-cache and my-branch
        if os.name == 'nt':
            cmd = ["./cadss-engine.exe", "-p", "my-processor", "-c", "my-cache", 
                   "-b", "my-branch", "-t", str(trace_file), "-s", str(config_file)]
        else:
            cmd = ["./cadss-engine", "-p", "my-processor", "-c", "my-cache", 
                   "-b", "my-branch", "-t", str(trace_file), "-s", str(config_file)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode != 0:
            print(f"  ERROR: Simulation failed")
            print(f"  stderr: {result.stderr[:200]}")
            return None
        
        # Parse the output
        output = result.stdout
        metrics = parse_simulator_output(output)
        
        # Get instruction count from trace file
        total_instructions = count_trace_instructions(trace_file)
        
        # Calculate AAT (Average Access Time per instruction)
        if total_instructions > 0 and metrics['ticks'] > 0:
            aat = metrics['ticks'] / total_instructions
        else:
            aat = 0.0
        
        return {
            'success': True,
            'raw_output': output,
            'ticks': metrics['ticks'],
            'total_instructions': total_instructions,
            'aat': aat
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ERROR: Simulation timed out")
        return None
    except Exception as e:
        print(f"  ERROR: Exception during simulation: {e}")
        return None

def main():
    """Main experiment runner."""
    # Check if simulator exists
    simulator_paths = ["./cadss-engine", "./cadss-engine.exe"]
    simulator_exists = any(os.path.exists(p) for p in simulator_paths)
    
    if not simulator_exists:
        print("Error: cadss-engine not found. Please build the project first.")
        print("Run: cmake . && make")
        return
    
    # Get trace files from integ directory
    trace_dir = Path("traces/integ")
    if not trace_dir.exists():
        print(f"Error: {trace_dir} directory not found")
        return
    
    trace_files = sorted(list(trace_dir.glob("*.trace")))
    if not trace_files:
        print(f"Error: No trace files found in {trace_dir}")
        return
    
    print("=" * 80)
    print("P3 INTEGRATION EXPERIMENT")
    print("=" * 80)
    print(f"\nFound {len(trace_files)} trace files:")
    for trace in trace_files:
        instr_count = count_trace_instructions(trace)
        instr_types = count_instruction_types(trace)
        print(f"  {trace.name}:")
        print(f"    Total instructions: {instr_count:,}")
        print(f"    ALU: {instr_types['A']:,}, Load: {instr_types['L']:,}, "
              f"Store: {instr_types['S']:,}, Branch: {instr_types['B']:,}")
    
    # Generate configurations
    print("\n" + "=" * 80)
    print("GENERATING CONFIGURATIONS")
    print("=" * 80)
    
    cache_configs = generate_cache_configs()
    branch_configs = generate_branch_configs()
    processor_configs = generate_processor_configs()
    
    print(f"\nCache configurations: {len(cache_configs)}")
    for config in cache_configs:
        print(f"  {config['type']}: s={config['s']}, E={config['E']}, b={config['b']}, "
              f"r={config['r']}, i={config['i']}, size={config['size']/1024:.1f}KB")
    
    print(f"\nBranch predictor configurations: {len(branch_configs)}")
    for config in branch_configs:
        print(f"  {config['type']}: s={config['s']}, b={config['b']}, g={config['g']}, "
              f"counters={config['counters']}")
    
    print(f"\nProcessor configurations: {len(processor_configs)}")
    for config in processor_configs:
        print(f"  {config['type']}: f={config['f']}, d={config['d']}, m={config['m']}, "
              f"j={config['j']}, k={config['k']}, c={config['c']}")
    
    total_experiments = len(cache_configs) * len(branch_configs) * len(processor_configs) * len(trace_files)
    print(f"\nTotal experiments: {total_experiments:,}")
    print("  (This may take a while...)")
    
    # Create results directory
    results_dir = Path("experiments_P3/experiment_results")
    results_dir.mkdir(exist_ok=True)
    
    # Prepare CSV output
    csv_file = results_dir / "integration_results.csv"
    fieldnames = [
        'exp_id', 'trace', 
        # Processor config
        'proc_type', 'fetch_rate', 'dispatch_mult', 'schedule_mult', 
        'fast_alu', 'long_alu', 'num_cdb',
        # Cache config
        'cache_type', 'cache_s', 'cache_E', 'cache_b', 'cache_r', 'cache_i', 'cache_size',
        # Branch config
        'branch_type', 'branch_s', 'branch_b', 'branch_g', 'branch_counters',
        # Results
        'simulation_success', 'total_instructions', 'ticks', 'aat', 
        'raw_output'
    ]
    
    print("\n" + "=" * 80)
    print("RUNNING EXPERIMENTS")
    print("=" * 80)
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        exp_id = 0
        
        for proc_config in processor_configs:
            for cache_config in cache_configs:
                for branch_config in branch_configs:
                    exp_id += 1
                    
                    # Create temporary config file
                    temp_config = results_dir / f"temp_config_{exp_id}.config"
                    create_config_file(proc_config, cache_config, branch_config, temp_config)
                    
                    print(f"\nExperiment {exp_id}/{total_experiments // len(trace_files)}:")
                    print(f"  Processor: {proc_config['type']}")
                    print(f"  Cache: {cache_config['type']}")
                    print(f"  Branch: {branch_config['type']}")
                    
                    for trace_file in trace_files:
                        trace_name = trace_file.stem
                        print(f"  Testing with {trace_name}...", end=" ")
                        
                        # Run simulation
                        result = run_simulation(str(temp_config), str(trace_file))
                        
                        if result:
                            print(f"✓ ticks={result['ticks']:,}, aat={result['aat']:.2f}")
                        else:
                            print("✗ FAILED")
                        
                        # Write results
                        row = {
                            'exp_id': exp_id,
                            'trace': trace_name,
                            # Processor config
                            'proc_type': proc_config['type'],
                            'fetch_rate': proc_config['f'],
                            'dispatch_mult': proc_config['d'],
                            'schedule_mult': proc_config['m'],
                            'fast_alu': proc_config['j'],
                            'long_alu': proc_config['k'],
                            'num_cdb': proc_config['c'],
                            # Cache config
                            'cache_type': cache_config['type'],
                            'cache_s': cache_config['s'],
                            'cache_E': cache_config['E'],
                            'cache_b': cache_config['b'],
                            'cache_r': cache_config['r'],
                            'cache_i': cache_config['i'],
                            'cache_size': cache_config['size'],
                            # Branch config
                            'branch_type': branch_config['type'],
                            'branch_s': branch_config['s'],
                            'branch_b': branch_config['b'],
                            'branch_g': branch_config['g'],
                            'branch_counters': branch_config['counters'],
                            # Results
                            'simulation_success': result is not None and result.get('success', False),
                            'total_instructions': result.get('total_instructions', 0) if result else 0,
                            'ticks': result.get('ticks', 0) if result else 0,
                            'aat': result.get('aat', 0.0) if result else 0.0,
                            'raw_output': result.get('raw_output', '') if result else ''
                        }
                        
                        writer.writerow(row)
                    
                    # Clean up temp config file
                    if temp_config.exists():
                        temp_config.unlink()
    
    print("\n" + "=" * 80)
    print("EXPERIMENT COMPLETED")
    print("=" * 80)
    print(f"Results saved to: {csv_file}")
    print(f"Total experiments run: {exp_id * len(trace_files):,}")

if __name__ == "__main__":
    main()
