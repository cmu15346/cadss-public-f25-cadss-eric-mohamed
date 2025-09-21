#!/usr/bin/env python3
"""
Quick test script to validate the cache experiment setup
"""

import subprocess
import os
from pathlib import Path

def test_simulator():
    """Test if the simulator runs correctly"""
    
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
    
    # Test with a simple configuration
    config_content = """__processor -p 1 // __other
__cache -E 1 -b 4 -s 8
// the name is "foo/*" and it takes three arguments
__foo/* -a 1 */
__branch
"""
    
    # Write test config
    with open("test_config.config", "w") as f:
        f.write(config_content)
    
    # Test with a trace file
    trace_files = list(Path("traces/cache").glob("*.trace"))
    if not trace_files:
        print("Error: No trace files found")
        return False
    
    test_trace = trace_files[0]
    print(f"Testing with trace: {test_trace}")
    
    try:
        # Use the correct command format: cadss-engine -c my-cache -t trace_file -s config_file
        cmd = [f"./{simulator_path}", "-c", "my-cache", "-t", str(test_trace), "-s", "test_config.config"]
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
        os.remove("test_config.config")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running simulator: {e}")
        return False

if __name__ == "__main__":
    print("Testing cache simulator setup...")
    if test_simulator():
        print("\nSimulator test PASSED! Ready to run experiments.")
    else:
        print("\nSimulator test FAILED! Please check the setup.")