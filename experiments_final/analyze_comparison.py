#!/usr/bin/env python3
"""
Perceptron vs Classic Predictor Analysis Script

Analyzes the results from perceptron_comparison.py to compare:
1. Perceptron vs Classic predictors with matched storage budgets
2. Impact of different indexing schemes (Standard, GShare, GSelect)
3. Performance vs storage tradeoffs
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


def load_results(csv_file):
    """Load and clean experiment results."""
    df = pd.read_csv(csv_file)
    
    # Filter successful simulations
    df = df[df['simulation_success'] == True].copy()
    
    # Convert numeric columns
    numeric_cols = ['s', 'b', 'g', 'storage_bits', 'ticks', 'total_branches',
                   'correct_predictions', 'mispredictions', 'accuracy', 'misprediction_rate']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Clean storage_diff_pct
    df['storage_diff_pct'] = pd.to_numeric(df['storage_diff_pct'], errors='coerce')
    
    return df


def analyze_matched_pairs(df):
    """Analyze matched pair comparisons."""
    matched_df = df[df['experiment_type'] == 'matched_pair'].copy()
    
    if len(matched_df) == 0:
        print("No matched pair data found")
        return None
    
    print("\n" + "="*70)
    print("MATCHED PAIR ANALYSIS")
    print("="*70)
    
    results = []
    
    # Group by matched pair IDs
    for trace in matched_df['trace'].unique():
        trace_df = matched_df[matched_df['trace'] == trace]
        
        # Find pairs
        classic_df = trace_df[trace_df['predictor_path'] == 'my-branch/']
        perc_df = trace_df[trace_df['predictor_path'] == 'final-project/']
        
        for _, classic_row in classic_df.iterrows():
            # Find matching perceptron
            perc_row = perc_df[perc_df['matched_classic_id'] == classic_row['config_id']]
            
            if len(perc_row) == 0:
                continue
            
            perc_row = perc_row.iloc[0]
            
            # Calculate improvements
            accuracy_improvement = perc_row['accuracy'] - classic_row['accuracy']
            mispred_rate_improvement = classic_row['misprediction_rate'] - perc_row['misprediction_rate']
            
            results.append({
                'trace': trace,
                'classic_type': classic_row['predictor_type'],
                'classic_accuracy': classic_row['accuracy'],
                'perceptron_type': perc_row['predictor_type'],
                'perceptron_accuracy': perc_row['accuracy'],
                'accuracy_improvement': accuracy_improvement,
                'mispred_rate_improvement': mispred_rate_improvement,
                'classic_storage': classic_row['storage_bits'],
                'perceptron_storage': perc_row['storage_bits'],
                'storage_diff_pct': perc_row['storage_diff_pct'],
                'classic_s': classic_row['s'],
                'classic_b': classic_row['b'],
                'perceptron_s': perc_row['s'],
                'perceptron_b': perc_row['b'],
            })
    
    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
        print("No valid matched pairs found")
        return None
    
    # Summary statistics by trace
    print("\nPerformance by Trace:")
    print("-" * 70)
    for trace in results_df['trace'].unique():
        trace_results = results_df[results_df['trace'] == trace]
        
        print(f"\n{trace}:")
        print(f"  Pairs tested: {len(trace_results)}")
        print(f"  Avg accuracy improvement: {trace_results['accuracy_improvement'].mean():.2f}%")
        print(f"  Avg mispred rate improvement: {trace_results['mispred_rate_improvement'].mean():.2f}%")
        print(f"  Perceptron wins: {sum(trace_results['accuracy_improvement'] > 0)} / {len(trace_results)}")
        
        # Best improvement
        best_idx = trace_results['accuracy_improvement'].idxmax()
        best = trace_results.loc[best_idx]
        print(f"  Best improvement: {best['accuracy_improvement']:.2f}% ({best['classic_type']} → {best['perceptron_type']})")
    
    # Overall statistics
    print("\n" + "-" * 70)
    print("OVERALL STATISTICS:")
    print("-" * 70)
    print(f"Total matched pairs: {len(results_df)}")
    print(f"Perceptron wins: {sum(results_df['accuracy_improvement'] > 0)} ({100*sum(results_df['accuracy_improvement'] > 0)/len(results_df):.1f}%)")
    print(f"Classic wins: {sum(results_df['accuracy_improvement'] < 0)} ({100*sum(results_df['accuracy_improvement'] < 0)/len(results_df):.1f}%)")
    print(f"Ties: {sum(results_df['accuracy_improvement'] == 0)}")
    print(f"\nAverage accuracy improvement: {results_df['accuracy_improvement'].mean():.2f}%")
    print(f"Median accuracy improvement: {results_df['accuracy_improvement'].median():.2f}%")
    print(f"Max improvement: {results_df['accuracy_improvement'].max():.2f}%")
    print(f"Max degradation: {results_df['accuracy_improvement'].min():.2f}%")
    
    return results_df


def analyze_by_predictor_type(df):
    """Analyze performance by predictor type."""
    print("\n" + "="*70)
    print("PERFORMANCE BY PREDICTOR TYPE")
    print("="*70)
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace]
        
        print(f"\n{trace}:")
        print("-" * 70)
        
        summary = trace_df.groupby('predictor_type').agg({
            'accuracy': ['mean', 'std', 'max'],
            'misprediction_rate': ['mean', 'std', 'min'],
            'storage_bits': ['mean', 'min', 'max'],
            'config_id': 'count'
        }).round(2)
        
        print(summary)


def analyze_storage_efficiency(df):
    """Analyze performance vs storage tradeoffs."""
    print("\n" + "="*70)
    print("STORAGE EFFICIENCY ANALYSIS")
    print("="*70)
    
    # For each predictor type, find best accuracy at different storage levels
    storage_bins = [0, 10000, 20000, 30000, 40000, 50000]
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace]
        
        print(f"\n{trace}:")
        print("-" * 70)
        
        for i in range(len(storage_bins)-1):
            bin_df = trace_df[(trace_df['storage_bits'] >= storage_bins[i]) & 
                            (trace_df['storage_bits'] < storage_bins[i+1])]
            
            if len(bin_df) == 0:
                continue
            
            print(f"\nStorage: {storage_bins[i]}-{storage_bins[i+1]} bits")
            
            best = bin_df.groupby('predictor_type')['accuracy'].agg(['max', 'mean', 'count'])
            print(best)


def create_visualizations(df, matched_df, output_dir):
    """Create visualization plots."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*70)
    print("CREATING VISUALIZATIONS")
    print("="*70)
    
    # 1. Matched Pair Comparison - Accuracy Improvement
    if matched_df is not None and len(matched_df) > 0:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Perceptron vs Classic Predictor: Matched Storage Budget Comparison', fontsize=16, fontweight='bold')
        
        traces = matched_df['trace'].unique()
        for idx, trace in enumerate(traces[:4]):
            ax = axes[idx // 2, idx % 2]
            trace_data = matched_df[matched_df['trace'] == trace]
            
            # Sort by classic type for better visualization
            trace_data = trace_data.sort_values('classic_type')
            
            x = range(len(trace_data))
            width = 0.35
            
            ax.bar([i - width/2 for i in x], trace_data['classic_accuracy'], 
                  width, label='Classic', alpha=0.8, color='steelblue')
            ax.bar([i + width/2 for i in x], trace_data['perceptron_accuracy'], 
                  width, label='Perceptron', alpha=0.8, color='coral')
            
            ax.set_xlabel('Configuration Pair')
            ax.set_ylabel('Accuracy (%)')
            ax.set_title(f'{trace}')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            
            # Add improvement percentages on top
            for i, row in enumerate(trace_data.itertuples()):
                improvement = row.accuracy_improvement
                color = 'green' if improvement > 0 else 'red'
                ax.text(i, max(row.classic_accuracy, row.perceptron_accuracy) + 1,
                       f'{improvement:+.1f}%', ha='center', fontsize=8, color=color, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(output_dir / 'matched_pairs_accuracy.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir / 'matched_pairs_accuracy.png'}")
        plt.close()
    
    # 2. Accuracy vs Storage (all configs)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Accuracy vs Storage Budget', fontsize=16, fontweight='bold')
    
    traces = df['trace'].unique()
    for idx, trace in enumerate(traces[:4]):
        ax = axes[idx // 2, idx % 2]
        trace_df = df[df['trace'] == trace]
        
        # Plot each predictor type
        for pred_type in trace_df['predictor_type'].unique():
            type_df = trace_df[trace_df['predictor_type'] == pred_type]
            marker = 'o' if 'Perceptron' in pred_type else 's'
            ax.scatter(type_df['storage_bits'], type_df['accuracy'], 
                      label=pred_type, alpha=0.6, s=50, marker=marker)
        
        ax.set_xlabel('Storage (bits)')
        ax.set_ylabel('Accuracy (%)')
        ax.set_title(f'{trace}')
        ax.legend(fontsize=8, loc='lower right')
        ax.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'accuracy_vs_storage.png', dpi=300, bbox_inches='tight')
    print(f"Saved: {output_dir / 'accuracy_vs_storage.png'}")
    plt.close()
    
    # 3. Misprediction Rate Comparison
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Box plot of misprediction rates by predictor type
    predictor_order = sorted(df['predictor_type'].unique())
    
    sns.boxplot(data=df, x='predictor_type', y='misprediction_rate', 
               order=predictor_order, ax=ax, palette='Set2')
    ax.set_xlabel('Predictor Type', fontsize=12)
    ax.set_ylabel('Misprediction Rate (%)', fontsize=12)
    ax.set_title('Misprediction Rate Distribution by Predictor Type', fontsize=14, fontweight='bold')
    ax.tick_params(axis='x', rotation=45)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_dir / 'misprediction_rate_comparison.png', dpi=300, bbox_inches='tight')
    print(f"Saved: {output_dir / 'misprediction_rate_comparison.png'}")
    plt.close()
    
    # 4. Impact of History Length (b parameter) for Perceptrons
    perc_df = df[df['predictor_path'] == 'final-project/']
    if len(perc_df) > 0:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Perceptron: Impact of History Length (b)', fontsize=16, fontweight='bold')
        
        for idx, trace in enumerate(traces[:4]):
            ax = axes[idx // 2, idx % 2]
            trace_perc = perc_df[perc_df['trace'] == trace]
            
            # Group by b and get mean accuracy for each indexing scheme
            for g_val, g_name in [(0, 'Standard'), (1, 'GShare'), (2, 'GSelect')]:
                g_df = trace_perc[trace_perc['g'] == g_val]
                if len(g_df) > 0:
                    b_accuracy = g_df.groupby('b')['accuracy'].mean()
                    ax.plot(b_accuracy.index, b_accuracy.values, marker='o', label=g_name, linewidth=2)
            
            ax.set_xlabel('History Length (b)')
            ax.set_ylabel('Average Accuracy (%)')
            ax.set_title(f'{trace}')
            ax.legend()
            ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_dir / 'perceptron_history_length_impact.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir / 'perceptron_history_length_impact.png'}")
        plt.close()
    
    # 5. Best Configuration Summary Table
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis('tight')
    ax.axis('off')
    
    # Find best config for each trace
    best_configs = []
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace]
        best = trace_df.loc[trace_df['accuracy'].idxmax()]
        
        best_configs.append([
            trace,
            best['predictor_type'],
            f"s={int(best['s'])}, b={int(best['b'])}, g={int(best['g'])}",
            f"{best['accuracy']:.2f}%",
            f"{best['misprediction_rate']:.2f}%",
            f"{int(best['storage_bits'])} bits"
        ])
    
    table = ax.table(cellText=best_configs,
                    colLabels=['Trace', 'Best Predictor', 'Config (s,b,g)', 'Accuracy', 'Mispred Rate', 'Storage'],
                    cellLoc='left',
                    loc='center',
                    colWidths=[0.15, 0.2, 0.2, 0.15, 0.15, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header
    for i in range(6):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(best_configs) + 1):
        for j in range(6):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')
    
    plt.title('Best Predictor Configuration for Each Trace', fontsize=14, fontweight='bold', pad=20)
    plt.savefig(output_dir / 'best_configurations.png', dpi=300, bbox_inches='tight')
    print(f"Saved: {output_dir / 'best_configurations.png'}")
    plt.close()


def generate_report(df, matched_df, output_file):
    """Generate text report."""
    with open(output_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("PERCEPTRON VS CLASSIC BRANCH PREDICTOR COMPARISON REPORT\n")
        f.write("="*70 + "\n\n")
        
        f.write("EXPERIMENT OVERVIEW\n")
        f.write("-"*70 + "\n")
        f.write(f"Total configurations tested: {len(df)}\n")
        f.write(f"Traces tested: {', '.join(df['trace'].unique())}\n")
        f.write(f"Predictor types: {', '.join(df['predictor_type'].unique())}\n\n")
        
        if matched_df is not None and len(matched_df) > 0:
            f.write("MATCHED PAIR RESULTS\n")
            f.write("-"*70 + "\n")
            f.write(f"Total matched pairs: {len(matched_df)}\n")
            f.write(f"Perceptron wins: {sum(matched_df['accuracy_improvement'] > 0)} ")
            f.write(f"({100*sum(matched_df['accuracy_improvement'] > 0)/len(matched_df):.1f}%)\n")
            f.write(f"Average accuracy improvement: {matched_df['accuracy_improvement'].mean():.2f}%\n\n")
            
            f.write("Best Improvements by Trace:\n")
            for trace in matched_df['trace'].unique():
                trace_data = matched_df[matched_df['trace'] == trace]
                best_idx = trace_data['accuracy_improvement'].idxmax()
                best = trace_data.loc[best_idx]
                f.write(f"\n  {trace}:\n")
                f.write(f"    {best['classic_type']} → {best['perceptron_type']}\n")
                f.write(f"    Improvement: {best['accuracy_improvement']:.2f}%\n")
                f.write(f"    Classic: {best['classic_accuracy']:.2f}% accuracy\n")
                f.write(f"    Perceptron: {best['perceptron_accuracy']:.2f}% accuracy\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("BEST OVERALL CONFIGURATIONS\n")
        f.write("="*70 + "\n\n")
        
        for trace in df['trace'].unique():
            trace_df = df[df['trace'] == trace]
            best = trace_df.loc[trace_df['accuracy'].idxmax()]
            
            f.write(f"{trace}:\n")
            f.write(f"  Predictor: {best['predictor_type']}\n")
            f.write(f"  Parameters: s={int(best['s'])}, b={int(best['b'])}, g={int(best['g'])}\n")
            f.write(f"  Accuracy: {best['accuracy']:.2f}%\n")
            f.write(f"  Misprediction Rate: {best['misprediction_rate']:.2f}%\n")
            f.write(f"  Storage: {int(best['storage_bits'])} bits\n\n")
    
    print(f"Saved: {output_file}")


def main():
    """Main analysis function."""
    results_file = Path("experiments_final/results/perceptron_comparison_results.csv")
    
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        print("Please run perceptron_comparison.py first")
        return
    
    print("Loading results...")
    df = load_results(results_file)
    
    print(f"Loaded {len(df)} successful experiments")
    
    # Run analyses
    matched_df = analyze_matched_pairs(df)
    analyze_by_predictor_type(df)
    analyze_storage_efficiency(df)
    
    # Create visualizations
    output_dir = Path("experiments_final/results/figures")
    create_visualizations(df, matched_df, output_dir)
    
    # Generate report
    report_file = Path("experiments_final/results/comparison_report.txt")
    generate_report(df, matched_df, report_file)
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"Results directory: experiments_final/results/")
    print(f"Figures directory: {output_dir}")
    print(f"Report: {report_file}")


if __name__ == "__main__":
    main()
