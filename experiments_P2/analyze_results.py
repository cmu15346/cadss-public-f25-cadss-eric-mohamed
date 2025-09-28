#!/usr/bin/env python3
"""
Branch Predictor Experiment Analysis Script

This script analyzes the results from branch_experiment.py to find
the optimal branch predictor configurations and study the impact of design parameters.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def load_and_clean_results(csv_file):
    """Load and clean the experiment results."""
    df = pd.read_csv(csv_file)
    
    # Filter successful simulations only
    df = df[df['simulation_success'] == True].copy()
    
    # Convert numeric columns
    numeric_cols = ['s', 'b', 'g', 'counters', 'predictor_size', 'bhr_size', 
                   'total_branches', 'total_lines', 'ticks', 'aat']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remove rows with invalid data
    df = df.dropna(subset=['ticks', 'aat'])
    df = df[df['ticks'] > 0]
    df = df[df['aat'] > 0]
    
    # Use AAT as the primary performance metric (lower is better)
    df['performance_metric'] = df['aat']
    df['metric_name'] = 'AAT (Average Access Time)'
    df['lower_is_better'] = True
    
    return df

def analyze_by_trace(df):
    """Analyze results for each trace separately."""
    results = {}
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace].copy()
        
        if len(trace_df) == 0:
            continue
        
        # Find best configuration based on performance metric
        if trace_df['lower_is_better'].iloc[0]:
            best_config = trace_df.loc[trace_df['performance_metric'].idxmin()]
        else:
            best_config = trace_df.loc[trace_df['performance_metric'].idxmax()]
        
        # Calculate statistics
        stats = {
            'trace': trace,
            'num_configs': len(trace_df),
            'best_config_id': best_config['config_id'],
            'best_performance': best_config['performance_metric'],
            'best_type': best_config['type'],
            'best_s': best_config['s'],
            'best_b': best_config['b'],
            'best_g': best_config['g'],
            'best_counters': best_config['counters'],
            'best_ticks': best_config.get('ticks', 0),
            'best_branches': best_config.get('total_branches', 0),
            'mean_performance': trace_df['performance_metric'].mean(),
            'std_performance': trace_df['performance_metric'].std(),
            'min_performance': trace_df['performance_metric'].min(),
            'max_performance': trace_df['performance_metric'].max()
        }
        
        results[trace] = stats
    
    return results

def analyze_2bit_vs_gselect(df):
    """Compare 2-bit vs GSELECT predictor performance."""
    results = {}
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace].copy()
        
        # Separate 2-bit and GSELECT results
        twobit_df = trace_df[trace_df['type'] == '2-bit']
        gselect_df = trace_df[trace_df['type'] == 'GSELECT']
        
        if len(twobit_df) == 0 or len(gselect_df) == 0:
            continue
        
        # Find best of each type
        best_2bit = twobit_df.loc[twobit_df['performance_metric'].idxmin()]
        best_gselect = gselect_df.loc[gselect_df['performance_metric'].idxmin()]
        
        # Calculate improvement
        improvement = (best_2bit['performance_metric'] - best_gselect['performance_metric']) / best_2bit['performance_metric'] * 100
        
        results[trace] = {
            'trace': trace,
            'best_2bit_aat': best_2bit['performance_metric'],
            'best_2bit_config': f"s={best_2bit['s']}",
            'best_gselect_aat': best_gselect['performance_metric'],
            'best_gselect_config': f"s={best_gselect['s']}, b={best_gselect['b']}",
            'gselect_improvement_percent': improvement,
            'winner': 'GSELECT' if best_gselect['performance_metric'] < best_2bit['performance_metric'] else '2-bit'
        }
    
    return results

def analyze_bhr_impact(df):
    """Analyze the impact of BHR size on GSELECT performance."""
    gselect_df = df[df['type'] == 'GSELECT'].copy()
    
    if len(gselect_df) == 0:
        return {}
    
    results = {}
    
    for trace in gselect_df['trace'].unique():
        trace_df = gselect_df[gselect_df['trace'] == trace]
        
        # Group by predictor size and analyze BHR impact
        bhr_analysis = {}
        
        for s in trace_df['s'].unique():
            s_df = trace_df[trace_df['s'] == s]
            if len(s_df) > 1:  # Need multiple BHR sizes to compare
                best_bhr = s_df.loc[s_df['performance_metric'].idxmin()]
                worst_bhr = s_df.loc[s_df['performance_metric'].idxmax()]
                
                bhr_analysis[f's={s}'] = {
                    'best_bhr': best_bhr['b'],
                    'best_aat': best_bhr['performance_metric'],
                    'worst_bhr': worst_bhr['b'],
                    'worst_aat': worst_bhr['performance_metric'],
                    'improvement': (worst_bhr['performance_metric'] - best_bhr['performance_metric']) / worst_bhr['performance_metric'] * 100
                }
        
        results[trace] = bhr_analysis
    
    return results

def find_universal_config(df):
    """Find the configuration that performs best across all traces."""
    
    # Calculate mean performance for each configuration across all traces
    config_performance = df.groupby('config_id').agg({
        'performance_metric': ['mean', 'std', 'min', 'max'],
        'trace': 'count',
        'type': 'first',
        's': 'first',
        'b': 'first',
        'g': 'first',
        'counters': 'first'
    }).round(4)
    
    # Flatten column names
    config_performance.columns = ['_'.join(col).strip() for col in config_performance.columns]
    
    # Only consider configurations tested on all traces
    num_traces = df['trace'].nunique()
    config_performance = config_performance[config_performance['trace_count'] == num_traces]
    
    if len(config_performance) == 0:
        print("Warning: No configuration was tested on all traces")
        return None
    
    # Find best configuration based on performance metric
    if df['lower_is_better'].iloc[0]:
        best_config_id = config_performance['performance_metric_mean'].idxmin()
    else:
        best_config_id = config_performance['performance_metric_mean'].idxmax()
    best_config = config_performance.loc[best_config_id]
    
    return best_config_id, best_config

def create_visualizations(df, output_dir):
    """Create visualizations focused on 2-bit vs GSELECT comparison and BHR analysis."""
    
    plt.style.use('default')
    fig_dir = Path(output_dir) / "figures"
    fig_dir.mkdir(exist_ok=True)
    
    # 1. 2-bit vs GSELECT comparison
    traces = df['trace'].unique()
    n_traces = len(traces)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes = axes.flatten()
    
    for i, trace in enumerate(traces[:4]):  # Limit to 4 traces for readability
        if i >= len(axes):
            break
            
        trace_df = df[df['trace'] == trace]
        
        # Plot 2-bit performance
        twobit_df = trace_df[trace_df['type'] == '2-bit']
        if len(twobit_df) > 0:
            axes[i].plot(twobit_df['s'], twobit_df['performance_metric'], 
                        'bo-', label='2-bit', linewidth=2, markersize=8)
        
        # Plot GSELECT performance (group by s, show best b for each s)
        gselect_df = trace_df[trace_df['type'] == 'GSELECT']
        if len(gselect_df) > 0:
            gselect_best = gselect_df.groupby('s')['performance_metric'].min().reset_index()
            axes[i].plot(gselect_best['s'], gselect_best['performance_metric'], 
                        'ro-', label='GSELECT (best b)', linewidth=2, markersize=8)
        
        axes[i].set_title(f'Trace: {trace}')
        axes[i].set_xlabel('Predictor Size (s)')
        axes[i].set_ylabel('AAT')
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)
    
    # Hide unused subplots
    for i in range(len(traces), len(axes)):
        axes[i].set_visible(False)
    
    plt.suptitle('2-bit vs GSELECT Predictor Comparison by Trace', fontsize=16)
    plt.tight_layout()
    plt.savefig(fig_dir / "2bit_vs_gselect_comparison.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. BHR Impact Analysis for GSELECT
    gselect_df = df[df['type'] == 'GSELECT']
    if len(gselect_df) > 0:
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, trace in enumerate(traces[:4]):
            if i >= len(axes):
                break
                
            trace_df = gselect_df[gselect_df['trace'] == trace]
            
            # Plot BHR impact for different predictor sizes
            for s in sorted(trace_df['s'].unique()):
                s_df = trace_df[trace_df['s'] == s]
                if len(s_df) > 1:  # Need multiple BHR values
                    axes[i].plot(s_df['b'], s_df['performance_metric'], 
                                'o-', label=f's={s}', linewidth=2, markersize=6)
            
            axes[i].set_title(f'BHR Impact - Trace: {trace}')
            axes[i].set_xlabel('BHR Size (b)')
            axes[i].set_ylabel('AAT')
            axes[i].legend()
            axes[i].grid(True, alpha=0.3)
        
        # Hide unused subplots
        for i in range(len(traces), len(axes)):
            axes[i].set_visible(False)
        
        plt.suptitle('Impact of BHR Size on GSELECT Performance', fontsize=16)
        plt.tight_layout()
        plt.savefig(fig_dir / "bhr_impact_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # 3. Heatmap of AAT by s and b (for GSELECT)
    gselect_df = df[df['type'] == 'GSELECT'].copy()
    if len(gselect_df) > 0:
        # Create average across all traces for the heatmap
        pivot_table = gselect_df.pivot_table(values='performance_metric', index='s', columns='b', aggfunc='mean')
        
        plt.figure(figsize=(12, 8))
        sns.heatmap(pivot_table, annot=True, fmt='.3f', cmap='RdYlBu_r', 
                   cbar_kws={'label': 'Average AAT'})
        plt.title('Average AAT by Predictor Size (s) and BHR Size (b) - GSELECT')
        plt.xlabel('BHR Size (b)')
        plt.ylabel('Predictor Size (s)')
        plt.tight_layout()
        plt.savefig(fig_dir / "gselect_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # 4. Overall Performance Summary
    plt.figure(figsize=(12, 8))
    
    # Box plot comparing 2-bit vs GSELECT
    plt.subplot(2, 2, 1)
    sns.boxplot(data=df, x='type', y='performance_metric')
    plt.title('AAT Distribution by Predictor Type')
    plt.ylabel('AAT')
    
    # Performance vs predictor size
    plt.subplot(2, 2, 2)
    for pred_type in df['type'].unique():
        type_df = df[df['type'] == pred_type]
        if pred_type == '2-bit':
            plt.plot(type_df['s'], type_df['performance_metric'], 'bo', 
                    label=pred_type, alpha=0.6, markersize=4)
        else:
            plt.scatter(type_df['s'], type_df['performance_metric'], 
                       c=type_df['b'], cmap='viridis', alpha=0.6, s=30)
    plt.xlabel('Predictor Size (s)')
    plt.ylabel('AAT')
    plt.title('AAT vs Predictor Size')
    plt.legend()
    
    # Best configuration per trace
    plt.subplot(2, 2, 3)
    trace_best = df.groupby(['trace', 'type'])['performance_metric'].min().reset_index()
    trace_pivot = trace_best.pivot(index='trace', columns='type', values='performance_metric')
    trace_pivot.plot(kind='bar', ax=plt.gca())
    plt.title('Best AAT by Trace and Type')
    plt.ylabel('AAT')
    plt.xticks(rotation=45)
    
    # Counter utilization
    plt.subplot(2, 2, 4)
    plt.hist(df['counters'], bins=15, alpha=0.7, edgecolor='black')
    plt.axvline(512, color='red', linestyle='--', label='Budget (512)')
    plt.xlabel('Counters Used')
    plt.ylabel('Frequency')
    plt.title('Counter Utilization')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(fig_dir / "performance_summary.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 5. Counter utilization analysis
    plt.figure(figsize=(10, 6))
    plt.hist(df['counters'], bins=20, alpha=0.7, edgecolor='black')
    plt.axvline(512, color='red', linestyle='--', label='Budget Limit (512)')
    plt.xlabel('Number of Counters Used')
    plt.ylabel('Number of Configurations')
    plt.title('Counter Utilization Distribution')
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "counter_utilization.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 6. Performance by trace
    if df['trace'].nunique() > 1:
        plt.figure(figsize=(14, 6))
        trace_stats = df.groupby('trace')['performance_metric'].agg(['mean', 'min' if df['lower_is_better'].iloc[0] else 'max']).reset_index()
        
        x = range(len(trace_stats))
        plt.bar(x, trace_stats['mean'], alpha=0.7, label=f'Mean {df["metric_name"].iloc[0]}')
        plt.bar(x, trace_stats.iloc[:, 2], alpha=0.7, label=f'Best {df["metric_name"].iloc[0]}')
        
        plt.xlabel('Trace')
        plt.ylabel(f'{df["metric_name"].iloc[0]}')
        plt.title(f'Predictor Performance by Trace')
        plt.xticks(x, trace_stats['trace'], rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_dir / "performance_by_trace.png", dpi=300, bbox_inches='tight')
        plt.close()

def generate_report(df, trace_results, universal_config, comparison_results, bhr_results, output_dir):
    """Generate a comprehensive analysis report focused on 2-bit vs GSELECT comparison."""
    
    report_file = Path(output_dir) / "branch_analysis_report.txt"
    
    with open(report_file, 'w') as f:
        f.write("BRANCH PREDICTOR FOCUSED ANALYSIS REPORT\n")
        f.write("COMPARING 2-BIT vs GSELECT PREDICTORS\n")
        f.write("="*50 + "\n\n")
        
        f.write(f"Total configurations tested: {df['config_id'].nunique()}\n")
        f.write(f"Total traces analyzed: {df['trace'].nunique()}\n")
        f.write(f"Total successful simulations: {len(df)}\n\n")
        
        # Overall statistics
        f.write("OVERALL STATISTICS\n")
        f.write("-" * 20 + "\n")
        metric_name = df['metric_name'].iloc[0]
        f.write(f"Mean {metric_name} across all configs/traces: {df['performance_metric'].mean():.4f}\n")
        f.write(f"Best {metric_name} found: {df['performance_metric'].min() if df['lower_is_better'].iloc[0] else df['performance_metric'].max():.4f}\n")
        f.write(f"Worst {metric_name} found: {df['performance_metric'].max() if df['lower_is_better'].iloc[0] else df['performance_metric'].min():.4f}\n")
        f.write(f"Standard deviation: {df['performance_metric'].std():.4f}\n\n")
        
        # 2-bit vs GSELECT Comparison
        f.write("2-BIT vs GSELECT COMPARISON\n")
        f.write("-" * 30 + "\n")
        for trace, results in comparison_results.items():
            f.write(f"\nTrace: {trace}\n")
            f.write(f"  Best 2-bit AAT: {results['best_2bit_aat']:.4f} ({results['best_2bit_config']})\n")
            f.write(f"  Best GSELECT AAT: {results['best_gselect_aat']:.4f} ({results['best_gselect_config']})\n")
            f.write(f"  GSELECT Improvement: {results['gselect_improvement_percent']:.1f}%\n")
            f.write(f"  Winner: {results['winner']}\n")
        
        # Overall comparison
        avg_improvement = sum(r['gselect_improvement_percent'] for r in comparison_results.values()) / len(comparison_results)
        gselect_wins = sum(1 for r in comparison_results.values() if r['winner'] == 'GSELECT')
        f.write(f"\nOVERALL COMPARISON SUMMARY:\n")
        f.write(f"  Average GSELECT improvement: {avg_improvement:.1f}%\n")
        f.write(f"  GSELECT wins: {gselect_wins}/{len(comparison_results)} traces\n")
        
        # BHR Impact Analysis
        f.write(f"\n\nBHR SIZE IMPACT ANALYSIS\n")
        f.write("-" * 25 + "\n")
        for trace, bhr_data in bhr_results.items():
            f.write(f"\nTrace: {trace}\n")
            for config, data in bhr_data.items():
                f.write(f"  {config}: Best BHR={data['best_bhr']} (AAT={data['best_aat']:.4f}), ")
                f.write(f"Worst BHR={data['worst_bhr']} (AAT={data['worst_aat']:.4f}), ")
                f.write(f"Improvement={data['improvement']:.1f}%\n")
        
        # Universal configuration
        if universal_config is not None:
            config_id, config_data = universal_config
            f.write(f"\n\nRECOMMENDED UNIVERSAL CONFIGURATION\n")
            f.write("-" * 35 + "\n")
            f.write(f"Configuration ID: {config_id}\n")
            f.write(f"Predictor Type: {config_data['type_first']}\n")
            f.write(f"Predictor size (s): {config_data['s_first']}\n")
            f.write(f"BHR size (b): {config_data['b_first']}\n")
            f.write(f"Model (g): {config_data['g_first']}\n")
            f.write(f"Total counters: {config_data['counters_first']}\n")
            f.write(f"Mean {metric_name}: {config_data['performance_metric_mean']:.4f}\n")
            f.write(f"{metric_name} Std Dev: {config_data['performance_metric_std']:.4f}\n\n")
        
        # Configuration type analysis
        f.write("PREDICTOR TYPE ANALYSIS\n")
        f.write("-" * 25 + "\n")
        type_analysis = df.groupby('type').agg({
            'performance_metric': ['count', 'mean', 'std', 'min' if df['lower_is_better'].iloc[0] else 'max'],
            'counters': 'mean'
        }).round(4)
        
        type_analysis.columns = ['_'.join(col).strip() for col in type_analysis.columns]
        
        for pred_type in type_analysis.index:
            data = type_analysis.loc[pred_type]
            f.write(f"\n{pred_type}:\n")
            f.write(f"  Configurations tested: {data['performance_metric_count']}\n")
            f.write(f"  Mean {metric_name}: {data['performance_metric_mean']:.4f}\n")
            f.write(f"  Best {metric_name}: {data[f'performance_metric_{"min" if df["lower_is_better"].iloc[0] else "max"}']:.4f}\n")
            f.write(f"  {metric_name} Std Dev: {data['performance_metric_std']:.4f}\n")
            f.write(f"  Average Counters: {data['counters_mean']:.1f}\n")
        
        # Per-trace results
        f.write("\nBEST CONFIGURATION PER TRACE\n")
        f.write("-" * 30 + "\n")
        for trace, stats in trace_results.items():
            f.write(f"\nTrace: {trace}\n")
            f.write(f"  Best Config ID: {stats['best_config_id']}\n")
            f.write(f"  Best {metric_name}: {stats['best_performance']:.4f}\n")
            f.write(f"  Total Ticks: {stats['best_ticks']}\n")
            f.write(f"  Total Branches: {stats['best_branches']}\n")
            f.write(f"  Configuration: {stats['best_type']} ")
            f.write(f"s={stats['best_s']} b={stats['best_b']} g={stats['best_g']}\n")
        
        # Counter utilization analysis
        f.write(f"\n\nCOUNTER UTILIZATION ANALYSIS\n")
        f.write("-" * 28 + "\n")
        f.write(f"Budget: 512 counters\n")
        f.write(f"Largest config tested: {df['counters'].max()} counters\n")
        f.write(f"Average config size: {df['counters'].mean():.0f} counters\n")
        f.write(f"Budget utilization: {df['counters'].max()/512*100:.1f}%\n")
        
        # BHR analysis
        if df['bhr_size'].max() > 0:
            f.write(f"\nBHR SIZE ANALYSIS\n")
            f.write("-" * 17 + "\n")
            f.write(f"BHR sizes tested: {sorted(df['bhr_size'].unique())}\n")
            
            # Compare performance with and without BHR
            no_bhr = df[df['bhr_size'] == 0]['performance_metric'].mean()
            with_bhr = df[df['bhr_size'] > 0]['performance_metric'].mean()
            f.write(f"Mean {metric_name} without BHR: {no_bhr:.4f}\n")
            f.write(f"Mean {metric_name} with BHR: {with_bhr:.4f}\n")
            
            improvement = (no_bhr - with_bhr) / no_bhr * 100 if df['lower_is_better'].iloc[0] else (with_bhr - no_bhr) / no_bhr * 100
            f.write(f"BHR improvement: {improvement:.1f}%\n")

def main():
    """Main analysis function."""
    
    results_file = Path("experiment_results/branch_experiment_results.csv")
    
    if not results_file.exists():
        print(f"Error: Results file {results_file} not found.")
        print("Please run branch_experiment.py first.")
        return
    
    print("Loading experiment results...")
    df = load_and_clean_results(results_file)
    
    if len(df) == 0:
        print("Error: No valid results found in the CSV file.")
        return
    
    print(f"Loaded {len(df)} successful simulation results")
    print(f"Covering {df['config_id'].nunique()} configurations and {df['trace'].nunique()} traces")
    print(f"Performance metric: {df['metric_name'].iloc[0]}")
    
    # Analyze results
    print("\nAnalyzing results by trace...")
    trace_results = analyze_by_trace(df)
    
    print("Comparing 2-bit vs GSELECT predictors...")
    comparison_results = analyze_2bit_vs_gselect(df)
    
    print("Analyzing BHR impact on GSELECT...")
    bhr_results = analyze_bhr_impact(df)
    
    print("Finding universal configuration...")
    universal_config = find_universal_config(df)
    
    # Create output directory
    output_dir = Path("experiment_results")
    
    print("Creating focused visualizations...")
    create_visualizations(df, output_dir)
    
    print("Generating focused analysis report...")
    generate_report(df, trace_results, universal_config, comparison_results, bhr_results, output_dir)
    
    # Print summary to console
    print("\n" + "="*60)
    print("FOCUSED EXPERIMENT SUMMARY: 2-BIT vs GSELECT")
    print("="*60)
    
    # Show comparison results
    if comparison_results:
        print("\n2-BIT vs GSELECT COMPARISON:")
        gselect_wins = sum(1 for r in comparison_results.values() if r['winner'] == 'GSELECT')
        avg_improvement = sum(r['gselect_improvement_percent'] for r in comparison_results.values()) / len(comparison_results)
        print(f"  GSELECT wins: {gselect_wins}/{len(comparison_results)} traces")
        print(f"  Average improvement: {avg_improvement:.1f}%")
        
        for trace, result in comparison_results.items():
            print(f"  {trace}: {result['winner']} wins ({result['gselect_improvement_percent']:.1f}% improvement)")
    
    if universal_config is not None:
        config_id, config_data = universal_config
        print(f"\nRECOMMENDED UNIVERSAL CONFIGURATION:")
        print(f"  Type: {config_data['type_first']}")
        print(f"  Parameters: s={config_data['s_first']} b={config_data['b_first']} g={config_data['g_first']}")
        print(f"  Counters: {config_data['counters_first']}")
        print(f"  Mean AAT: {config_data['performance_metric_mean']:.4f}")
    
    print(f"\nDetailed focused analysis saved to: experiment_results/branch_analysis_report.txt")
    print(f"Focused visualizations saved to: experiment_results/figures/")
    print(f"  - 2-bit vs GSELECT comparison plots")
    print(f"  - BHR impact analysis for GSELECT")
    print(f"  - Performance summary and heatmaps")

if __name__ == "__main__":
    main()