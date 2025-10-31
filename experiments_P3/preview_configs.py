#!/usr/bin/env python3
"""
Preview P3 Integration Experiment Configurations

This script shows what configurations will be tested without running simulations.
"""

import sys
sys.path.append('.')

from integration_experiment import (
    generate_cache_configs,
    generate_branch_configs,
    generate_processor_configs,
    count_trace_instructions,
    count_instruction_types
)
from pathlib import Path

def main():
    """Preview configurations."""
    print("=" * 80)
    print("P3 INTEGRATION EXPERIMENT - CONFIGURATION PREVIEW")
    print("=" * 80)
    
    # Trace files
    trace_dir = Path("traces/integ")
    if trace_dir.exists():
        trace_files = sorted(list(trace_dir.glob("*.trace")))
        print(f"\n📁 TRACE FILES ({len(trace_files)} total):")
        print("-" * 80)
        for trace in trace_files:
            instr_count = count_trace_instructions(trace)
            instr_types = count_instruction_types(trace)
            size_mb = trace.stat().st_size / (1024 * 1024)
            print(f"\n  {trace.name} ({size_mb:.1f} MB)")
            print(f"    Total instructions: {instr_count:,}")
            print(f"    ALU: {instr_types['A']:,} ({100*instr_types['A']/instr_count:.1f}%)")
            print(f"    Load: {instr_types['L']:,} ({100*instr_types['L']/instr_count:.1f}%)")
            print(f"    Store: {instr_types['S']:,} ({100*instr_types['S']/instr_count:.1f}%)")
            print(f"    Branch: {instr_types['B']:,} ({100*instr_types['B']/instr_count:.1f}%)")
    else:
        print(f"\n⚠️  Warning: {trace_dir} not found")
        trace_files = []
    
    # Processor configurations
    processor_configs = generate_processor_configs()
    print(f"\n\n🖥️  PROCESSOR CONFIGURATIONS ({len(processor_configs)} total):")
    print("-" * 80)
    print(f"\n{'Type':<25} {'f':<4} {'d':<4} {'m':<4} {'j':<4} {'k':<4} {'c':<4}")
    print("-" * 80)
    for config in processor_configs:
        print(f"{config['type']:<25} {config['f']:<4} {config['d']:<4} "
              f"{config['m']:<4} {config['j']:<4} {config['k']:<4} {config['c']:<4}")
    
    print("\nLegend:")
    print("  f = fetch rate (instructions per cycle)")
    print("  d = dispatch multiplier")
    print("  m = schedule multiplier (RS entries per FU)")
    print("  j = number of fast ALU FUs (1 cycle latency)")
    print("  k = number of long ALU FUs (3 cycle latency)")
    print("  c = number of Common Data Buses (CDBs)")
    
    # Cache configurations
    cache_configs = generate_cache_configs()
    print(f"\n\n💾 CACHE CONFIGURATIONS ({len(cache_configs)} total):")
    print("-" * 80)
    print(f"\n{'Type':<20} {'Sets':<8} {'Ways':<6} {'Block':<8} {'RRIP':<6} {'Victim':<8} {'Size':<10}")
    print("-" * 80)
    for config in cache_configs:
        sets = 2 ** config['s']
        block = 2 ** config['b']
        size_kb = config['size'] / 1024
        rrip = f"{config['r']}-bit" if config['r'] > 0 else "-"
        victim = f"{config['i']} ent." if config['i'] > 0 else "-"
        print(f"{config['type']:<20} {sets:<8} {config['E']:<6} {block:<8} "
              f"{rrip:<6} {victim:<8} {size_kb:>8.1f}KB")
    
    # Branch predictor configurations
    branch_configs = generate_branch_configs()
    print(f"\n\n🌳 BRANCH PREDICTOR CONFIGURATIONS ({len(branch_configs)} total):")
    print("-" * 80)
    print(f"\n{'Type':<20} {'Counters':<10} {'BHR bits':<10} {'Model':<10}")
    print("-" * 80)
    for config in branch_configs:
        model_map = {0: '2-bit', 1: 'GSHARE', 2: 'GSELECT', 3: 'Yeh-Patt'}
        model = model_map.get(config['g'], 'Unknown')
        bhr = str(config['b']) if config['b'] > 0 else '-'
        print(f"{config['type']:<20} {config['counters']:<10} {bhr:<10} {model:<10}")
    
    # Summary
    total_experiments = len(processor_configs) * len(cache_configs) * len(branch_configs) * len(trace_files)
    
    print("\n\n📊 EXPERIMENT SUMMARY:")
    print("=" * 80)
    print(f"  Processor configs:  {len(processor_configs)}")
    print(f"  Cache configs:      {len(cache_configs)}")
    print(f"  Branch configs:     {len(branch_configs)}")
    print(f"  Trace files:        {len(trace_files)}")
    print("-" * 80)
    print(f"  Total experiments:  {total_experiments:,}")
    
    # Estimate runtime
    if total_experiments > 0:
        # Rough estimate: 2-10 seconds per simulation depending on trace size
        avg_time = 5  # seconds per simulation
        total_seconds = total_experiments * avg_time
        hours = total_seconds / 3600
        
        print(f"\n  Estimated runtime:  ~{hours:.1f} hours")
        print(f"                      (assuming ~{avg_time}s per simulation)")
    
    print("\n💡 TIP: Start with a smaller subset first to verify everything works!")
    print("   You can modify the config generation functions to test fewer configs.")
    
    print("\n" + "=" * 80)
    print("Ready to run? Execute: python experiments_P3/integration_experiment.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
