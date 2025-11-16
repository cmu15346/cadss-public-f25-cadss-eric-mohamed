#!/usr/bin/env python3
"""
Preview the configurations that will be tested in the coherence experiment.

This script shows what configurations will be generated without actually
running any simulations, helping you understand the experiment scope.
"""

from pathlib import Path

# Import from the experiment script
import sys
sys.path.insert(0, str(Path(__file__).parent))

def preview_configurations():
    """Preview all configurations that will be tested."""
    
    print("=" * 80)
    print("COHERENCE EXPERIMENT CONFIGURATION PREVIEW")
    print("=" * 80)
    
    # Coherence schemes
    coherence_schemes = {
        'MI': 0,
        'MSI': 1,
        'MESI': 2,
        'MOESI': 3,
        'MESIF': 4
    }
    
    # Processor counts
    processor_counts = [2, 4, 8]
    
    print("\n1. COHERENCE PROTOCOLS")
    print("-" * 40)
    for scheme, scheme_id in coherence_schemes.items():
        print(f"   {scheme} (id={scheme_id})")
    
    print("\n2. PROCESSOR COUNTS")
    print("-" * 40)
    for count in processor_counts:
        print(f"   {count} processors")
    
    print("\n3. TASKGRAPH TRACES")
    print("-" * 40)
    
    # Try to find traces
    afs_trace_dir = Path("/afs/cs.cmu.edu/academic/class/15346-f23/public/traces/coher")
    local_trace_dir = Path("traces/coher")
    
    traces = []
    if afs_trace_dir.exists():
        traces = sorted(list(afs_trace_dir.glob("*.taskgraph")))
        print(f"   Found {len(traces)} traces in AFS:")
    elif local_trace_dir.exists():
        traces = sorted(list(local_trace_dir.glob("*.taskgraph")))
        print(f"   Found {len(traces)} traces locally:")
    else:
        print("   ⚠ No traces found!")
        print("   Expected locations:")
        print(f"     - {afs_trace_dir}")
        print(f"     - {local_trace_dir}")
        traces = []
    
    if traces:
        for trace in traces[:10]:  # Show first 10
            print(f"     • {trace.name}")
        if len(traces) > 10:
            print(f"     ... and {len(traces) - 10} more")
    
    print("\n4. EXPERIMENT SCOPE")
    print("-" * 40)
    
    num_protocols = len(coherence_schemes)
    num_proc_counts = len(processor_counts)
    num_traces = len(traces) if traces else 0
    
    total_configs = num_protocols * num_proc_counts
    total_experiments = total_configs * num_traces
    
    print(f"   Protocols: {num_protocols}")
    print(f"   Processor counts: {num_proc_counts}")
    print(f"   Unique configurations: {total_configs}")
    print(f"   Traces: {num_traces}")
    print(f"   Total experiments: {total_experiments}")
    
    print("\n5. ESTIMATED TIME")
    print("-" * 40)
    
    if total_experiments > 0:
        # Rough estimate: 10-30 seconds per experiment
        min_time = total_experiments * 10
        max_time = total_experiments * 30
        
        print(f"   Assuming 10-30s per simulation:")
        print(f"   Minimum: {min_time/60:.0f} minutes ({min_time/3600:.1f} hours)")
        print(f"   Maximum: {max_time/60:.0f} minutes ({max_time/3600:.1f} hours)")
    else:
        print("   Cannot estimate - no traces found")
    
    print("\n6. CONFIGURATION MATRIX")
    print("-" * 40)
    print("\n   Protocol × Processor Count Matrix:")
    print("   " + "-" * 60)
    
    # Header
    header = "   Protocol  |"
    for pc in processor_counts:
        header += f" {pc:2d}p |"
    print(header)
    print("   " + "-" * 60)
    
    # Rows
    for scheme in coherence_schemes.keys():
        row = f"   {scheme:8s}  |"
        for pc in processor_counts:
            row += f"  ✓  |"
        print(row)
    
    print("   " + "-" * 60)
    
    print("\n7. EXAMPLE CONFIGURATIONS")
    print("-" * 40)
    
    examples = [
        ("MI", 2, "Baseline: Simple invalidation protocol with 2 processors"),
        ("MSI", 4, "Mid-range: Shared state with 4 processors"),
        ("MESI", 8, "Advanced: Exclusive state with 8 processors"),
        ("MOESI", 4, "Complex: Owned state with 4 processors"),
        ("MESIF", 2, "Advanced: Forward state with 2 processors")
    ]
    
    for i, (protocol, procs, desc) in enumerate(examples, 1):
        print(f"\n   Example {i}: {protocol} with {procs} processors")
        print(f"   {desc}")
        print(f"   Config: coherence_id={coherence_schemes[protocol]}, processors={procs}")
    
    print("\n" + "=" * 80)
    
    if traces:
        print("✓ Ready to run experiments")
        print("\nTo proceed:")
        print("  python experiments_P5/coherence_experiment.py")
    else:
        print("⚠ Cannot run experiments - no traces found")
        print("\nPlease ensure taskgraph traces are available")
    
    print("=" * 80)

if __name__ == "__main__":
    preview_configurations()
