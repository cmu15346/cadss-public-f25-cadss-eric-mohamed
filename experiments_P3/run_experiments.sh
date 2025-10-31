#!/bin/bash
#
# WSL wrapper script to run P3 integration experiments
#
# Usage:
#   ./run_experiments.sh          - Run full experiment
#   ./run_experiments.sh preview  - Preview configurations
#   ./run_experiments.sh test     - Run single test
#   ./run_experiments.sh analyze  - Analyze results
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================================================="
echo "P3 Integration Experiments - WSL Runner"
echo "=============================================================================="

case "${1:-run}" in
    preview)
        echo "Previewing configurations..."
        python3 experiments_P3/preview_configs.py
        ;;
    
    test)
        echo "Running single configuration test..."
        python3 experiments_P3/test_single.py
        ;;
    
    analyze)
        echo "Analyzing results..."
        if [ ! -f "experiments_P3/experiment_results/integration_results.csv" ]; then
            echo "Error: No results found!"
            echo "Please run experiments first: ./run_experiments.sh"
            exit 1
        fi
        python3 experiments_P3/analyze_results.py
        ;;
    
    run)
        echo "Starting full experiment suite..."
        echo ""
        echo "This will run 1,680 simulations across:"
        echo "  - 7 processor configurations"
        echo "  - 10 cache configurations"
        echo "  - 8 branch predictor configurations"
        echo "  - 3 trace files"
        echo ""
        echo "Estimated time: ~2-3 hours"
        echo ""
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 experiments_P3/integration_experiment.py
            echo ""
            echo "=============================================================================="
            echo "Experiments complete! Run analysis with:"
            echo "  ./run_experiments.sh analyze"
            echo "=============================================================================="
        else
            echo "Cancelled."
        fi
        ;;
    
    *)
        echo "Unknown command: $1"
        echo ""
        echo "Usage:"
        echo "  ./run_experiments.sh          - Run full experiment"
        echo "  ./run_experiments.sh preview  - Preview configurations"
        echo "  ./run_experiments.sh test     - Run single test"
        echo "  ./run_experiments.sh analyze  - Analyze results"
        exit 1
        ;;
esac
