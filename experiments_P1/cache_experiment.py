#!/usr/bin/env python3
"""
Cache Configuration Experiment Script

This script runs cache simulations with different configurations
to find the optimal cache design within a 54KB budget.
"""

import subprocess
import csv
import os
import math
import itertools
from pathlib import Path

def calculate_cache_size(s, E, b, r=0, i=0, use_rrip=False):
    """
    Calculate total cache size in bytes.
    
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

def generate_configurations(max_size_bytes=54 * 1024):
    """
    Generate all valid cache configurations within the size budget.
    
    Returns:
        List of configuration dictionaries
    """
    configurations = []
    
    # Parameter ranges to explore
    s_range = range(6, 18)  # 64 to 256K sets
    E_range = range(1, 33)  # 1- to 32-way associative
    b_range = range(4, 11)   # 16B to 1024B blocks (limit specified by handout)
    r_range = range(2, 7)   # 2-6 RRIP bits
    i_range = range(0, 9)  # 0-8 victim cache entries (limit specified by handout)

    # Generate all combinations
    for s, E, b in itertools.product(s_range, E_range, b_range):
        
        # Configuration 1: LRU only (no victim cache)
        size = calculate_cache_size(s, E, b, use_rrip=False)
        if size <= max_size_bytes:
            configurations.append({
                'type': 'LRU',
                's': s, 'E': E, 'b': b, 'r': 0, 'i': 0,
                'size': size
            })
        
        # Configuration 2: RRIP only (no victim cache)
        for r in r_range:
            size = calculate_cache_size(s, E, b, r=r, use_rrip=True)
            if size <= max_size_bytes:
                configurations.append({
                    'type': 'RRIP',
                    's': s, 'E': E, 'b': b, 'r': r, 'i': 0,
                    'size': size
                })
        
        # Configuration 3: LRU + Victim Cache
        for i in i_range[1:]:  # Skip 0 as it's already covered
            size = calculate_cache_size(s, E, b, i=i, use_rrip=False)
            if size <= max_size_bytes:
                configurations.append({
                    'type': 'LRU+Victim',
                    's': s, 'E': E, 'b': b, 'r': 0, 'i': i,
                    'size': size
                })
        
        # Configuration 4: RRIP + Victim Cache (NEW!)
        for r in r_range:
            for i in i_range[1:]:  # Skip 0
                size = calculate_cache_size(s, E, b, r=r, i=i, use_rrip=True)
                if size <= max_size_bytes:
                    configurations.append({
                        'type': 'RRIP+Victim',
                        's': s, 'E': E, 'b': b, 'r': r, 'i': i,
                        'size': size
                    })
    
    print(f"Generated {len(configurations)} configurations before sampling")

    # Sample an equal number of configs of each type
    type_counts = {}
    for config in configurations:
        ctype = config['type']
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

    # Find the minimum count across all types
    min_count = min(type_counts.values(), default=0)

    # Filter configurations to keep only the minimum number per type
    filtered_configs = []
    for config in configurations:
        ctype = config['type']
        if type_counts[ctype] > min_count:
            type_counts[ctype] -= 1
        else:
            filtered_configs.append(config)

    # Sort by size to prioritize larger configurations
    filtered_configs.sort(key=lambda x: x['size'], reverse=True)
    configurations = filtered_configs

    # Evenly sample configurations to get a diverse set
    step = max(1, len(configurations) // 200)  # Aim for ~200 configurations
    sampled_configs = configurations[::step]
    return sampled_configs

def create_config_file(config, config_path):
    """Create a configuration file for the simulator."""
    with open(config_path, 'w') as f:
        f.write("__processor -p 1 // __other\n")
        
        # Build cache arguments
        cache_args = f"__cache -E {config['E']} -b {config['b']} -s {config['s']}"
        
        if config['i'] > 0:
            cache_args += f" -i {config['i']}"
        
        if config['r'] > 0:
            cache_args += f" -R {config['r']}"
        
        f.write(cache_args + "\n")
        f.write("// the name is \"foo/*\" and it takes three arguments\n")
        f.write("__foo/* -a 1 */\n")
        f.write("__branch\n")

def parse_simulator_output(output):
    """
    Parse the simulator output to extract performance metrics.
    
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {
        'ticks': 0,
        'aat': 0.0
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

def count_trace_accesses(trace_file):
    """
    Count the total number of memory accesses in a trace file.
    Each line represents one access.
    
    Returns:
        Number of accesses (lines) in the trace file
    """
    try:
        with open(trace_file, 'r') as f:
            return sum(1 for line in f if line.strip())
    except Exception as e:
        print(f"Error counting accesses in {trace_file}: {e}")
        return 0

def run_simulation(config_file, trace_file):
    """
    Run the cache simulator and parse the output.
    
    Returns:
        Dictionary with simulation results or None if failed
    """
    try:
        # Use the correct command format: cadss-engine -c my-cache -t trace_file -s config_file
        if os.name == 'nt':
            cmd = ["./cadss-engine.exe", "-c", "my-cache", "-t", trace_file, "-s", config_file]
        else:
            cmd = ["./cadss-engine", "-c", "my-cache", "-t", trace_file, "-s", config_file]
            
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"Simulation failed for {config_file} with {trace_file}")
            print(f"Error: {result.stderr}")
            return None
        
        # Parse the output to extract ticks
        output = result.stdout
        metrics = parse_simulator_output(output)
        
        # Count total accesses from trace file
        total_accesses = count_trace_accesses(trace_file)
        
        # Calculate AAT = Total Ticks / Total Accesses
        if total_accesses > 0 and metrics['ticks'] > 0:
            aat = metrics['ticks'] / total_accesses
        else:
            aat = 0.0
        
        return {
            'success': True,
            'raw_output': output,
            'ticks': metrics['ticks'],
            'total_accesses': total_accesses,
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
    if not os.path.exists("./cadss-engine"):
        print("Error: cadss-engine not found. Please build the project first.")
        return
    
    # Get list of trace files
    trace_dir = Path("traces/afs-cache")
    if not trace_dir.exists():
        print("Error: traces/afs-cache directory not found")
        return
    
    trace_files = list(trace_dir.glob("*.trace"))
    if not trace_files:
        print("Error: No trace files found in traces/afs-cache/")
        return
    
    print(f"Found {len(trace_files)} trace files")
    
    # Generate configurations
    print("Generating cache configurations...")
    configurations = generate_configurations()
    print(f"Generated {len(configurations)} configurations within 54KB budget")
    
    # Show configuration type distribution
    config_types = {}
    for config in configurations:
        config_type = config['type']
        config_types[config_type] = config_types.get(config_type, 0) + 1
    
    print("\nConfiguration breakdown:")
    for config_type, count in config_types.items():
        print(f"  {config_type}: {count} configurations")
    
    print(f"\nSize range: {min(c['size'] for c in configurations)} - {max(c['size'] for c in configurations)} bytes")
    print(f"            {min(c['size'] for c in configurations)/1024:.1f} - {max(c['size'] for c in configurations)/1024:.1f} KB")
    
    # Create results directory
    results_dir = Path("experiment_results")
    results_dir.mkdir(exist_ok=True)
    
    # Prepare CSV output
    csv_file = results_dir / "cache_experiment_results.csv"
    fieldnames = ['config_id', 'trace', 'type', 's', 'E', 'b', 'r', 'i', 'size_bytes', 
                  'simulation_success', 'total_accesses', 'ticks', 'aat', 'raw_output']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        config_id = 0
        for config in configurations:
            config_id += 1
            
            # Create temporary config file
            temp_config = results_dir / f"temp_config_{config_id}.config"
            create_config_file(config, temp_config)
            
            print(f"Testing configuration {config_id}/{len(configurations)}: "
                  f"{config['type']} s={config['s']} E={config['E']} b={config['b']} "
                  f"r={config['r']} i={config['i']} size={config['size']}B")
            
            for trace_file in trace_files:
                trace_name = trace_file.stem
                
                # Run simulation
                result = run_simulation(str(temp_config), str(trace_file))
                
                # Write results
                row = {
                    'config_id': config_id,
                    'trace': trace_name,
                    'type': config['type'],
                    's': config['s'],
                    'E': config['E'],
                    'b': config['b'],
                    'r': config['r'],
                    'i': config['i'],
                    'size_bytes': config['size'],
                    'simulation_success': result is not None and result.get('success', False),
                    'total_accesses': result.get('total_accesses', 0) if result else 0,
                    'ticks': result.get('ticks', 0) if result else 0,
                    'aat': result.get('aat', 0.0) if result else 0.0,
                    'raw_output': result.get('raw_output', '') if result else ''
                }
                
                writer.writerow(row)
            
            # Clean up temp config file
            temp_config.unlink()
            
            # Optional: break early for testing (remove or increase for full experiment)
            # if config_id >= 10:  # Limit to first 10 configs for testing
            #     print("Limiting to first 10 configurations for testing")
            #     break
    
    print(f"Experiment completed. Results saved to {csv_file}")
    print(f"Tested {min(config_id, len(configurations))} configurations "
          f"across {len(trace_files)} trace files")

if __name__ == "__main__":
    main()