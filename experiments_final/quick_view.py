#!/usr/bin/env python3
"""
Quick Results Viewer - Shows sample comparisons from the experiment
"""

import pandas as pd
from pathlib import Path

def main():
    results_file = Path("experiments_final/results/perceptron_comparison_results.csv")
    
    if not results_file.exists():
        print("Results file not found. Please run the experiment first.")
        return
    
    df = pd.read_csv(results_file)
    df = df[df['simulation_success'] == True].copy()
    
    print("="*80)
    print("BRANCH PREDICTOR COMPARISON - SAMPLE RESULTS")
    print("="*80)
    
    # Show some interesting matched pairs
    matched = df[df['experiment_type'] == 'matched_pair'].copy()
    
    for trace in ['black-test', 'cadss', 'fluid-test', 'ls']:
        trace_df = matched[matched['trace'] == trace]
        
        if len(trace_df) == 0:
            continue
        
        print(f"\n{'='*80}")
        print(f"TRACE: {trace}")
        print(f"{'='*80}")
        
        # Find a few interesting pairs
        classic = trace_df[trace_df['predictor_path'] == 'my-branch/'].copy()
        perc = trace_df[trace_df['predictor_path'] == 'final-project/'].copy()
        
        # Merge to create pairs
        pairs = []
        for _, c_row in classic.iterrows():
            p_row = perc[perc['matched_classic_id'] == c_row['config_id']]
            if len(p_row) > 0:
                p_row = p_row.iloc[0]
                pairs.append({
                    'classic_type': c_row['predictor_type'],
                    'classic_config': f"s={int(c_row['s'])}, b={int(c_row['b'])}, g={int(c_row['g'])}",
                    'classic_acc': c_row['accuracy'],
                    'classic_storage': int(c_row['storage_bits']),
                    'perc_type': p_row['predictor_type'],
                    'perc_config': f"s={int(p_row['s'])}, b={int(p_row['b'])}, g={int(p_row['g'])}",
                    'perc_acc': p_row['accuracy'],
                    'perc_storage': int(p_row['storage_bits']),
                    'improvement': p_row['accuracy'] - c_row['accuracy']
                })
        
        if len(pairs) == 0:
            continue
        
        # Show best improvement
        pairs_df = pd.DataFrame(pairs)
        best_idx = pairs_df['improvement'].idxmax()
        best = pairs_df.iloc[best_idx]
        
        print(f"\n🏆 BEST IMPROVEMENT: {best['improvement']:+.2f}%")
        print(f"  Classic:    {best['classic_type']:12s} {best['classic_config']:20s} → {best['classic_acc']:.2f}% ({best['classic_storage']:6d} bits)")
        print(f"  Perceptron: {best['perc_type']:12s} {best['perc_config']:20s} → {best['perc_acc']:.2f}% ({best['perc_storage']:6d} bits)")
        
        # Show worst case
        worst_idx = pairs_df['improvement'].idxmin()
        worst = pairs_df.iloc[worst_idx]
        
        print(f"\n📉 WORST CASE: {worst['improvement']:+.2f}%")
        print(f"  Classic:    {worst['classic_type']:12s} {worst['classic_config']:20s} → {worst['classic_acc']:.2f}% ({worst['classic_storage']:6d} bits)")
        print(f"  Perceptron: {worst['perc_type']:12s} {worst['perc_config']:20s} → {worst['perc_acc']:.2f}% ({worst['perc_storage']:6d} bits)")
        
        # Show average
        avg_improvement = pairs_df['improvement'].mean()
        wins = sum(pairs_df['improvement'] > 0)
        total = len(pairs_df)
        
        print(f"\n📊 STATISTICS:")
        print(f"  Average improvement: {avg_improvement:+.2f}%")
        print(f"  Perceptron wins: {wins}/{total} ({100*wins/total:.1f}%)")
        print(f"  Classic wins: {total-wins}/{total} ({100*(total-wins)/total:.1f}%)")
    
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    # Overall stats
    total_matched = len(matched)
    classic_all = matched[matched['predictor_path'] == 'my-branch/']
    perc_all = matched[matched['predictor_path'] == 'final-project/']
    
    print(f"\nTotal matched pair experiments: {total_matched}")
    print(f"Classic predictor runs: {len(classic_all)}")
    print(f"Perceptron predictor runs: {len(perc_all)}")
    
    print(f"\nAverage accuracy:")
    print(f"  Classic predictors: {classic_all['accuracy'].mean():.2f}%")
    print(f"  Perceptron predictors: {perc_all['accuracy'].mean():.2f}%")
    print(f"  Difference: {perc_all['accuracy'].mean() - classic_all['accuracy'].mean():+.2f}%")
    
    print(f"\nFor detailed analysis, see:")
    print(f"  - experiments_final/results/comparison_report.txt")
    print(f"  - experiments_final/results/figures/*.png")
    print(f"  - experiments_final/RESULTS_SUMMARY.md")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
