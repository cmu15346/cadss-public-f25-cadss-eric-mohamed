#!/usr/bin/env python3
"""
P5 Coherence Protocol Experiment Script

This script runs coherence protocol simulations with different configurations
to analyze the performance of different coherence protocols (MI, MSI, MESI, MOESI, MESIF).

The script tests:
1. All five coherence protocols (MI, MSI, MESI, MOESI, MESIF)
2. Multiple processor counts (2, 4, 8 processors)
3. Different taskgraph traces with varying sharing patterns
"""

import subprocess
import csv
import os
import json
import time
from pathlib import Path
import random

# Coherence protocol schemes
COHERENCE_SCHEMES = {
    'MI': 0,
    'MSI': 1,
    'MESI': 2,
    'MOESI': 3,
    'MESIF': 4
}

def generate_coherence_configs():
    """
    Generate coherence protocol configurations to test.
    
    Returns:
        List of configuration dictionaries
    """
    configurations = []
    
    # Test each coherence scheme
    for scheme_name, scheme_id in COHERENCE_SCHEMES.items():
        configurations.append({
            'scheme': scheme_name,
            'scheme_id': scheme_id
        })
    
    return configurations

def generate_processor_configs():
    """
    Generate processor count configurations.
    Testing with different numbers of processors to see protocol scaling.
    
    Returns:
        List of processor counts to test
    """
    return [2, 4]

def create_config_file(coherence_scheme_id, processor_count, config_path):
    """
    Create a configuration file for the coherence simulator.
    
    Args:
        coherence_scheme_id: ID of the coherence scheme (0-4)
        processor_count: Number of processors
        config_path: Path to save the config file
    """
    with open(config_path, 'w') as f:
        # Processor configuration - simple setup for coherence testing
        f.write(f"__processor -p {processor_count}\n")
        
        # Simple cache configuration for coherence testing
        # Using simpleCache which supports multiple processors
        f.write("__cache -E 4 -b 6 -s 8\n")
        
        # Coherence scheme
        f.write(f"__coherence -s {coherence_scheme_id}\n")
        
        # Interconnect and memory (required)
        f.write("__interconnect\n")
        f.write("__memory\n")

def parse_simulator_output(output):
    """
    Parse the simulator output to extract performance metrics.
    
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {
        'ticks': 0,
        'real_time': 0.0,
        'user_time': 0.0,
        'sys_time': 0.0,
        'memory_kb': 0
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
        
        # Look for timing information (JSON format)
        if line.startswith('{') and 'real' in line:
            try:
                timing = json.loads(line)
                metrics['real_time'] = float(timing.get('real', 0))
                metrics['user_time'] = float(timing.get('user', 0))
                metrics['sys_time'] = float(timing.get('sys', 0))
                metrics['memory_kb'] = int(timing.get('mem', 0))
            except:
                pass
    
    return metrics

def run_simulation(config_file, trace_file, processor_count, timeout=300):
    """
    Run the coherence simulator and parse the output.
    
    Args:
        config_file: Path to configuration file
        trace_file: Path to trace file (taskgraph)
        processor_count: Number of processors
        timeout: Timeout in seconds
    
    Returns:
        Dictionary with simulation results or None if failed
    """
    try:
        # Build command
        # Based on the handout example:
        # /usr/bin/time ./cadss-engine -s ex_proc.config -t <trace.taskgraph> -n 4 -c simpleCache
        # The coherence scheme is specified in the config file, not via -h flag
        if os.name == 'nt':
            # On Windows, use WSL to run the Linux executable
            # Convert Windows paths to WSL paths
            wsl_config = str(config_file).replace('\\', '/').replace('D:', '/mnt/d')
            wsl_trace = str(trace_file).replace('\\', '/').replace('D:', '/mnt/d')
            
            cmd = [
                "wsl",
                "/usr/bin/time",
                "./cadss-engine",
                "-s", wsl_config,
                "-t", wsl_trace,
                "-n", str(processor_count),
                "-c", "simpleCache"
            ]
        else:
            cmd = [
                "/usr/bin/time",
                "./cadss-engine",
                "-s", str(config_file),
                "-t", str(trace_file),
                "-n", str(processor_count),
                "-c", "simpleCache"
            ]
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        if result.returncode != 0:
            print(f"  ERROR: Simulation failed")
            print(f"  stderr: {result.stderr[:300]}")
            return None
        
        # Parse the output
        output = result.stdout
        metrics = parse_simulator_output(output)
        
        # If we didn't get timing info from output, use measured time
        if metrics['real_time'] == 0:
            metrics['real_time'] = elapsed_time
        
        return {
            'success': True,
            'raw_output': output,
            'ticks': metrics['ticks'],
            'real_time': metrics['real_time'],
            'user_time': metrics['user_time'],
            'sys_time': metrics['sys_time'],
            'memory_kb': metrics['memory_kb']
        }
        
    except subprocess.TimeoutExpired:
        print(f"  ERROR: Simulation timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"  ERROR: Exception during simulation: {e}")
        return None

def get_taskgraph_traces():
    """
    Find available taskgraph traces for coherence testing.
    
    Returns:
        List of paths to taskgraph files
    """
    # Try the AFS path first (if on Shark machines)
    afs_trace_dir = Path("/afs/cs.cmu.edu/academic/class/15346-f23/public/traces/coher")
    
    traces = []
    
    if afs_trace_dir.exists():
        # Get taskgraph files from AFS
        traces = sorted(list(afs_trace_dir.glob("*.taskgraph")))
    else:
        # Try local traces directory
        local_trace_dir = Path("traces/coher")
        if local_trace_dir.exists():
            traces = sorted(list(local_trace_dir.glob("*.taskgraph")))

    return traces

def get_trace_name(trace_path):
    """
    Extract a clean trace name from the path.
    
    Args:
        trace_path: Path to trace file
    
    Returns:
        Clean trace name
    """
    name = trace_path.stem
    # Remove common suffixes for cleaner names
    name = name.replace('_simsmall', '').replace('_simlarge', '').replace('_simmedium', '')
    return name

def main():
    """Main experiment runner."""
    print("=" * 80)
    print("P5 COHERENCE PROTOCOL EXPERIMENT")
    print("=" * 80)
    
    # Check if simulator exists
    if os.name == 'nt':
        # On Windows, check if WSL and the executable exist
        try:
            result = subprocess.run(["wsl", "test", "-f", "./cadss-engine"], 
                                  capture_output=True, timeout=5)
            if result.returncode != 0:
                print("Error: cadss-engine not found in WSL.")
                print("Please build the project first:")
                print("  wsl")
                print("  cmake . && make")
                return
            print("✓ Found cadss-engine in WSL")
        except Exception as e:
            print(f"Error: Cannot access WSL: {e}")
            print("Please ensure WSL is installed and working.")
            return
    else:
        if not os.path.exists("./cadss-engine"):
            print("Error: cadss-engine not found. Please build the project first.")
            print("Run: cmake . && make")
            return
    
    # Get taskgraph traces
    print("\nSearching for taskgraph traces...")
    trace_files = get_taskgraph_traces()
    
    if not trace_files:
        print("Error: No taskgraph files found.")
        print("Please ensure taskgraph traces are available in:")
        print("  /afs/cs.cmu.edu/academic/class/15346-f23/public/traces/coher/")
        print("  OR traces/coher/")
        return
    
    print(f"Found {len(trace_files)} taskgraph trace files:")
    for trace in trace_files:
        print(f"  - {trace.name}")
    
    # Generate configurations
    print("\n" + "=" * 80)
    print("GENERATING CONFIGURATIONS")
    print("=" * 80)
    
    coherence_configs = generate_coherence_configs()
    processor_configs = generate_processor_configs()
    
    print(f"\nCoherence protocols to test: {len(coherence_configs)}")
    for config in coherence_configs:
        print(f"  - {config['scheme']} (id={config['scheme_id']})")
    
    print(f"\nProcessor counts to test: {processor_configs}")
    
    total_experiments = len(coherence_configs) * len(processor_configs) * len(trace_files)
    print(f"\nTotal experiments: {total_experiments:,}")
    print("  (This may take a while...)")
    
    # Create results directory
    results_dir = Path("experiments_P5/experiment_results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare CSV output
    csv_file = results_dir / "coherence_results.csv"
    fieldnames = [
        'exp_id', 'trace', 'trace_file',
        'coherence_scheme', 'coherence_id', 'processor_count',
        'simulation_success', 'ticks', 'real_time', 'user_time', 
        'sys_time', 'memory_kb', 'raw_output'
    ]
    
    print("\n" + "=" * 80)
    print("RUNNING EXPERIMENTS")
    print("=" * 80)
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        exp_id = 0
        
        for coherence_config in coherence_configs:
            for processor_count in processor_configs:
                exp_id += 1
                
                # Create temporary config file
                temp_config = results_dir / f"temp_config_{exp_id}.config"
                create_config_file(
                    coherence_config['scheme_id'],
                    processor_count,
                    temp_config
                )
                
                print(f"\nConfiguration {exp_id}/{len(coherence_configs) * len(processor_configs)}:")
                print(f"  Protocol: {coherence_config['scheme']}")
                print(f"  Processors: {processor_count}")
                
                for trace_file in trace_files:
                    trace_name = get_trace_name(trace_file)
                    print(f"  Testing with {trace_name}...", end=" ", flush=True)
                    
                    # Run simulation
                    result = run_simulation(
                        str(temp_config), 
                        str(trace_file), 
                        processor_count
                    )
                    
                    if result:
                        print(f"✓ ticks={result['ticks']:,}, time={result['real_time']:.2f}s")
                    else:
                        print("✗ FAILED")
                    
                    # Write results
                    row = {
                        'exp_id': exp_id,
                        'trace': trace_name,
                        'trace_file': str(trace_file),
                        'coherence_scheme': coherence_config['scheme'],
                        'coherence_id': coherence_config['scheme_id'],
                        'processor_count': processor_count,
                        'simulation_success': result is not None and result.get('success', False),
                        'ticks': result.get('ticks', 0) if result else 0,
                        'real_time': result.get('real_time', 0.0) if result else 0.0,
                        'user_time': result.get('user_time', 0.0) if result else 0.0,
                        'sys_time': result.get('sys_time', 0.0) if result else 0.0,
                        'memory_kb': result.get('memory_kb', 0) if result else 0,
                        'raw_output': result.get('raw_output', '') if result else ''
                    }
                    
                    writer.writerow(row)
                    csvfile.flush()  # Flush after each experiment
                
                # Clean up temp config file
                if temp_config.exists():
                    temp_config.unlink()
    
    print("\n" + "=" * 80)
    print("EXPERIMENT COMPLETED")
    print("=" * 80)
    print(f"Results saved to: {csv_file}")
    print(f"Total experiments run: {total_experiments:,}")
    print("\nNext steps:")
    print("  1. Run analyze_results.py to generate analysis and visualizations")
    print("  2. Review the results for your report")

if __name__ == "__main__":
    main()
