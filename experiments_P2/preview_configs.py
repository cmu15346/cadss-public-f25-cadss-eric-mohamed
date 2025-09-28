#!/usr/bin/env python3
"""
Configuration Preview Script

Shows what branch predictor configurations will be tested without running simulations.
"""

import sys
import os

# Add the current directory to path to import from branch_experiment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from branch_experiment import generate_configurations

def preview_configurations():
    """Preview all configurations that will be tested."""
    
    print("Branch Predictor Configuration Preview")
    print("=" * 50)
    
    configurations = generate_configurations()
    
    print(f"Total configurations within 512 counter budget: {len(configurations)}")
    
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
    b_values = sorted(set(c['b'] for c in configurations))
    g_values = sorted(set(c['g'] for c in configurations))
    
    print(f"\nParameter Ranges:")
    print("-" * 20)
    print(f"  Predictor size (s):  {s_values}")
    print(f"  BHR size (b):        {b_values}")
    print(f"  Model type (g):      {g_values}")
    
    # Counter analysis
    counters = [c['counters'] for c in configurations]
    print(f"\nCounter Usage Analysis:")
    print("-" * 23)
    print(f"  Smallest config:  {min(counters):6d} counters")
    print(f"  Largest config:   {max(counters):6d} counters")
    print(f"  Average counters: {sum(counters)/len(counters):6.0f} counters")
    print(f"  Budget:           {512:6d} counters")
    print(f"  Budget usage:     {max(counters)/512*100:5.1f}%")
    
    # Show some example configurations
    print(f"\nExample Configurations:")
    print("-" * 25)
    print("Type            s  b  g  Counters")
    print("-" * 35)
    
    # Show examples of each type
    shown_types = set()
    for config in configurations[:20]:  # Show first 20
        config_type = config['type']
        if config_type not in shown_types or len(shown_types) < 3:
            print(f"{config_type:<15} {config['s']:2d} {config['b']:2d} {config['g']:2d} "
                  f"{config['counters']:8d}")
            shown_types.add(config_type)
        
        if len(shown_types) >= 3:  # Show at least one of each type
            break
    
    # Estimate runtime
    num_traces = 4  # Estimated based on available branch traces
    total_simulations = len(configurations) * num_traces
    estimated_seconds_per_sim = 0.05  # Branch prediction is typically faster
    estimated_total_minutes = (total_simulations * estimated_seconds_per_sim) / 60
    
    print(f"\nRuntime Estimate:")
    print("-" * 17)
    print(f"  Total simulations: {total_simulations:,}")
    print(f"  Estimated time:    {estimated_total_minutes:.0f} minutes ({estimated_total_minutes/60:.1f} hours)")
    print(f"  Per configuration: {estimated_total_minutes/len(configurations):.1f} minutes")

if __name__ == "__main__":
    preview_configurations()