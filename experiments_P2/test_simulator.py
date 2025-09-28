#!/usr/bin/env python3
"""
Quick test script to validate the branch predictor experiment setup
"""

import subprocess
import os
from pathlib import Path

def test_simulator():
    """Test if the simulator runs correctly with branch predictor"""
    
    # Check if simulator exists
    simulator_names = ["cadss-engine", "cadss-engine.exe"]
    simulator_path = None
    
    for name in simulator_names:
        if os.path.exists(name):
            simulator_path = name
            break
    
    if not simulator_path:
        print("Error: Simulator not found. Looking for cadss-engine or cadss-engine.exe")
        return False
    
    print(f"Found simulator: {simulator_path}")
    
    # Test with a simple branch predictor configuration
    config_content = """__processor -p 1 // __other
__cache -E 1 -b 4 -s 8
// the name is "foo/*" and it takes three arguments
__foo/* -a 1 */
__branch -s 7 -b 2 -g 0
"""
    
    # Write test config
    with open("test_branch_config.config", "w") as f:
        f.write(config_content)
    
    # Test with available trace files
    trace_candidates = [
        Path("traces/ls-proc.trace"),
        Path("traces/branch/test.trace"),
        Path("traces/example.trace")
    ]
    
    test_trace = None
    for trace in trace_candidates:
        if trace.exists():
            test_trace = trace
            break
    
    if not test_trace:
        print("Error: No suitable trace files found")
        return False
    
    print(f"Testing with trace: {test_trace}")
    
    try:
        # Use the correct command format for branch prediction: cadss-engine -s config_file -t trace_file -b my-branch
        cmd = [f"./{simulator_path}", "-s", "test_branch_config.config", "-t", str(test_trace), "-b", "my-branch"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        print(f"Return code: {result.returncode}")
        print(f"Output length: {len(result.stdout)} characters")
        
        if result.stdout:
            print("First 500 characters of output:")
            print(result.stdout[:500])
        
        if result.stderr:
            print("Error output:")
            print(result.stderr)
        
        # Clean up
        os.remove("test_branch_config.config")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running simulator: {e}")
        return False

if __name__ == "__main__":
    print("Testing branch predictor simulator setup...")
    if test_simulator():
        print("\nBranch predictor simulator test PASSED! Ready to run experiments.")
    else:
        print("\nBranch predictor simulator test FAILED! Please check the setup.")