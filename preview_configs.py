#!/usr/bin/env python3
"""
Configuration Preview Script

Shows what cache configurations will be tested without running simulations.
"""

import sys
import os

# Add the current directory to path to import from cache_experiment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cache_experiment import generate_configurations

def preview_configurations():
    """Preview all configurations that will be tested."""
    
    print("Cache Configuration Preview")
    print("=" * 50)
    
    configurations = generate_configurations()
    
    print(f"Total configurations within 54KB budget: {len(configurations)}")
    
    # Show configuration type distribution
    config_types = {}
    for config in configurations:
        config_type = config['type']
        config_types[config_type] = config_types.get(config_type, 0) + 1
    
    print("\nConfiguration Type Breakdown:")
    print("-" * 30)
    total_configs = len(configurations)
    for config_type, count in sorted(config_types.items()):
        percentage = (count / total_configs) * 100
        print(f"  {config_type:<15}: {count:4d} configs ({percentage:5.1f}%)")
    
    # Show parameter ranges
    s_values = sorted(set(c['s'] for c in configurations))
    E_values = sorted(set(c['E'] for c in configurations))
    b_values = sorted(set(c['b'] for c in configurations))
    r_values = sorted(set(c['r'] for c in configurations if c['r'] > 0))
    i_values = sorted(set(c['i'] for c in configurations if c['i'] > 0))
    
    print(f"\nParameter Ranges:")
    print("-" * 20)
    print(f"  Set bits (s):        {s_values}")
    print(f"  Associativity (E):   {E_values}")
    print(f"  Block bits (b):      {b_values}")
    print(f"  RRIP bits (r):       {r_values}")
    print(f"  Victim entries (i):  {i_values}")
    
    # Size analysis
    sizes = [c['size'] for c in configurations]
    print(f"\nSize Analysis:")
    print("-" * 15)
    print(f"  Smallest config: {min(sizes):6d} bytes ({min(sizes)/1024:5.1f} KB)")
    print(f"  Largest config:  {max(sizes):6d} bytes ({max(sizes)/1024:5.1f} KB)")
    print(f"  Average size:    {sum(sizes)/len(sizes):6.0f} bytes ({sum(sizes)/len(sizes)/1024:5.1f} KB)")
    print(f"  Budget:          {54*1024:6d} bytes ({54:5.1f} KB)")
    print(f"  Budget usage:    {max(sizes)/(54*1024)*100:5.1f}%")
    
    # Show some example configurations
    print(f"\nExample Configurations:")
    print("-" * 25)
    print("Type            s  E  b  r  i  Size(KB)")
    print("-" * 40)
    
    # Show examples of each type
    shown_types = set()
    for config in configurations[:20]:  # Show first 20
        config_type = config['type']
        if config_type not in shown_types or len(shown_types) < 4:
            print(f"{config_type:<15} {config['s']:2d} {config['E']:2d} {config['b']:2d} "
                  f"{config['r']:2d} {config['i']:2d} {config['size']/1024:7.1f}")
            shown_types.add(config_type)
        
        if len(shown_types) >= 4:  # Show at least one of each type
            break
    
    # Estimate runtime
    num_traces = 12  # Based on the traces in traces/cache/
    total_simulations = len(configurations) * num_traces
    estimated_seconds_per_sim = 0.1  # Conservative estimate
    estimated_total_minutes = (total_simulations * estimated_seconds_per_sim) / 60
    
    print(f"\nRuntime Estimate:")
    print("-" * 17)
    print(f"  Total simulations: {total_simulations:,}")
    print(f"  Estimated time:    {estimated_total_minutes:.0f} minutes ({estimated_total_minutes/60:.1f} hours)")
    print(f"  Per configuration: {estimated_total_minutes/len(configurations):.1f} minutes")

if __name__ == "__main__":
    preview_configurations()