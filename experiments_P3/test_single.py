#!/usr/bin/env python3
"""
Test Single Configuration

Quick test script to verify the simulator works with one configuration
before running the full experiment suite.
"""

import subprocess
import os
from pathlib import Path

def create_test_config():
    """Create a simple test configuration."""
    config_content = """__processor -f 2 -d 1 -m 2 -j 2 -k 1 -c 2
__cache -E 2 -b 6 -s 7
__branch -s 7 -b 2 -g 2
"""
    
    config_path = Path("experiments_P3/test_single.config")
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    return config_path

def run_test():
    """Run a single test simulation."""
    print("=" * 80)
    print("TESTING SINGLE CONFIGURATION")
    print("=" * 80)
    
    # Check if simulator exists
    if not os.path.exists("./cadss-engine") and not os.path.exists("./cadss-engine.exe"):
        print("\n❌ Error: cadss-engine not found!")
        print("   Please build the project first:")
        print("   $ cmake .")
        print("   $ make")
        return False
    
    # Check if trace exists
    trace_path = Path("traces/integ/black.trace")
    if not trace_path.exists():
        print(f"\n❌ Error: {trace_path} not found!")
        return False
    
    # Create test config
    print("\n📝 Creating test configuration...")
    config_path = create_test_config()
    print(f"   Config: {config_path}")
    print("\n   Configuration details:")
    print("   - Processor: f=2, d=1, m=2, j=2, k=1, c=2 (Balanced)")
    print("   - Cache: 16KB 2-way LRU (s=7, E=2, b=6)")
    print("   - Branch: GSELECT with 128 counters, 2-bit BHR")
    
    # Run simulation
    print(f"\n🚀 Running simulation with {trace_path.name}...")
    
    try:
        if os.name == 'nt':
            cmd = ["./cadss-engine.exe", "-p", "my-processor", "-c", "my-cache",
                   "-b", "my-branch", "-t", str(trace_path), "-s", str(config_path)]
        else:
            cmd = ["./cadss-engine", "-p", "my-processor", "-c", "my-cache",
                   "-b", "my-branch", "-t", str(trace_path), "-s", str(config_path)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print("\n❌ Simulation failed!")
            print(f"\nstdout:\n{result.stdout}")
            print(f"\nstderr:\n{result.stderr}")
            return False
        
        # Parse output
        output = result.stdout
        print("\n✅ Simulation succeeded!")
        print("\n" + "-" * 80)
        print("OUTPUT:")
        print("-" * 80)
        print(output)
        print("-" * 80)
        
        # Extract ticks
        for line in output.split('\n'):
            if line.strip().startswith('Ticks - '):
                ticks = int(line.split('- ')[1])
                
                # Count instructions
                instr_count = 0
                with open(trace_path, 'r') as f:
                    instr_count = sum(1 for line in f if line.strip() and not line.startswith('//'))
                
                aat = ticks / instr_count
                ipc = instr_count / ticks
                
                print("\n📊 METRICS:")
                print(f"   Total ticks: {ticks:,}")
                print(f"   Total instructions: {instr_count:,}")
                print(f"   AAT (ticks/instruction): {aat:.2f}")
                print(f"   IPC (instructions/cycle): {ipc:.3f}")
        
        print("\n✅ Test complete! The simulator is working correctly.")
        print("\n💡 Ready to run full experiment:")
        print("   $ python experiments_P3/integration_experiment.py")
        
        # Clean up
        config_path.unlink()
        
        return True
        
    except subprocess.TimeoutExpired:
        print("\n❌ Simulation timed out!")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = run_test()
    exit(0 if success else 1)
