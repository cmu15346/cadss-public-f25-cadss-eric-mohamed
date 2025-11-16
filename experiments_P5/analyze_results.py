#!/usr/bin/env python3
"""
P5 Coherence Protocol Results Analysis Script

This script analyzes the results from coherence_experiment.py to:
1. Compare performance of different coherence protocols (MI, MSI, MESI, MOESI, MESIF)
2. Analyze protocol scaling with different processor counts
3. Evaluate protocol performance on different workloads/sharing patterns
4. Identify the benefits of introducing different coherence states
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

def load_results(csv_file):
    """Load experiment results from CSV."""
    df = pd.read_csv(csv_file)
    
    # Filter out failed simulations
    df = df[df['simulation_success'] == True].copy()
    
    # Convert to numeric
    numeric_cols = ['ticks', 'real_time', 'processor_count', 'coherence_id']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Drop rows with invalid data
    df = df.dropna(subset=['ticks'])
    df = df[df['ticks'] > 0]
    
    return df

def analyze_protocol_performance(df):
    """Analyze and compare performance of different coherence protocols."""
    print("=" * 80)
    print("COHERENCE PROTOCOL PERFORMANCE COMPARISON")
    print("=" * 80)
    
    # Overall performance by protocol
    protocol_perf = df.groupby('coherence_scheme').agg({
        'ticks': ['mean', 'std', 'min', 'max'],
        'real_time': 'mean',
        'trace': 'count'
    }).round(2)
    
    protocol_perf.columns = ['_'.join(col).strip() for col in protocol_perf.columns]
    protocol_perf = protocol_perf.sort_values('ticks_mean')
    
    print("\nOverall performance by coherence protocol:")
    print(protocol_perf.to_string())
    
    # Find best protocol
    best_protocol = protocol_perf.index[0]
    print(f"\n✓ Best overall protocol: {best_protocol}")
    print(f"  Average ticks: {protocol_perf.loc[best_protocol, 'ticks_mean']:,.0f}")
    
    # Calculate improvement over MI (baseline)
    if 'MI' in protocol_perf.index:
        mi_ticks = protocol_perf.loc['MI', 'ticks_mean']
        print(f"\nImprovement over MI protocol:")
        for protocol in protocol_perf.index:
            if protocol != 'MI':
                improvement = ((mi_ticks - protocol_perf.loc[protocol, 'ticks_mean']) / mi_ticks) * 100
                print(f"  {protocol}: {improvement:+.1f}%")
    
    return protocol_perf

def analyze_state_benefits(df):
    """
    Analyze the benefit of introducing different coherence states.
    Compare protocols to understand what each additional state provides.
    """
    print("\n" + "=" * 80)
    print("BENEFIT OF INTRODUCING DIFFERENT COHERENCE STATES")
    print("=" * 80)
    
    # Average ticks by protocol
    protocol_avg = df.groupby('coherence_scheme')['ticks'].mean().to_dict()
    
    # Define protocol progression and states they introduce
    comparisons = [
        ('MI', 'MSI', 'Shared (S) state', 
         'Allows multiple readers without invalidation'),
        ('MSI', 'MESI', 'Exclusive (E) state',
         'Reduces bus traffic for exclusive read'),
        ('MESI', 'MOESI', 'Owned (O) state',
         'Allows dirty sharing (one owner, multiple sharers)'),
        ('MESI', 'MESIF', 'Forward (F) state',
         'Designates single responder for shared data')
    ]
    
    print("\nState-by-state benefit analysis:")
    print("-" * 80)
    
    for base_proto, new_proto, state_name, description in comparisons:
        if base_proto in protocol_avg and new_proto in protocol_avg:
            base_ticks = protocol_avg[base_proto]
            new_ticks = protocol_avg[new_proto]
            improvement = ((base_ticks - new_ticks) / base_ticks) * 100
            
            print(f"\n{base_proto} → {new_proto}: Adding {state_name}")
            print(f"  Purpose: {description}")
            print(f"  {base_proto} avg ticks: {base_ticks:,.0f}")
            print(f"  {new_proto} avg ticks: {new_ticks:,.0f}")
            print(f"  Improvement: {improvement:+.1f}%")
            
            if improvement > 0:
                print(f"  ✓ {state_name} provides significant benefit")
            elif improvement > -5:
                print(f"  ≈ {state_name} provides marginal benefit")
            else:
                print(f"  ✗ {state_name} may add overhead for this workload")

def analyze_processor_scaling(df):
    """Analyze how protocols scale with different processor counts."""
    print("\n" + "=" * 80)
    print("PROTOCOL SCALING WITH PROCESSOR COUNT")
    print("=" * 80)
    
    for protocol in sorted(df['coherence_scheme'].unique()):
        protocol_df = df[df['coherence_scheme'] == protocol]
        
        scaling = protocol_df.groupby('processor_count').agg({
            'ticks': ['mean', 'std'],
            'trace': 'count'
        }).round(2)
        
        print(f"\n{protocol} Protocol Scaling:")
        print(scaling.to_string())
        
        # Calculate scaling efficiency
        proc_counts = sorted(protocol_df['processor_count'].unique())
        if len(proc_counts) > 1:
            baseline = protocol_df[protocol_df['processor_count'] == proc_counts[0]]['ticks'].mean()
            print(f"\n  Scaling efficiency (vs {proc_counts[0]} processors):")
            for proc_count in proc_counts:
                avg_ticks = protocol_df[protocol_df['processor_count'] == proc_count]['ticks'].mean()
                overhead = ((avg_ticks - baseline) / baseline) * 100
                print(f"    {proc_count} processors: {overhead:+.1f}% overhead")

def analyze_workload_sensitivity(df):
    """Analyze how different protocols perform on different workloads."""
    print("\n" + "=" * 80)
    print("WORKLOAD SENSITIVITY ANALYSIS")
    print("=" * 80)
    
    # Performance by trace and protocol
    workload_perf = df.pivot_table(
        index='trace',
        columns='coherence_scheme',
        values='ticks',
        aggfunc='mean'
    ).round(0)
    
    print("\nAverage ticks by workload and protocol:")
    print(workload_perf.to_string())
    
    # Find best protocol for each workload
    print("\n" + "-" * 80)
    print("Best protocol per workload:")
    for trace in workload_perf.index:
        best_protocol = workload_perf.loc[trace].idxmin()
        best_ticks = workload_perf.loc[trace].min()
        worst_protocol = workload_perf.loc[trace].idxmax()
        worst_ticks = workload_perf.loc[trace].max()
        
        improvement = ((worst_ticks - best_ticks) / worst_ticks) * 100
        
        print(f"\n  {trace}:")
        print(f"    Best: {best_protocol} ({best_ticks:,.0f} ticks)")
        print(f"    Worst: {worst_protocol} ({worst_ticks:,.0f} ticks)")
        print(f"    Range: {improvement:.1f}% difference")
    
    return workload_perf

def analyze_sharing_patterns(df):
    """
    Analyze which protocols work best for different sharing patterns.
    Infer sharing patterns from trace characteristics and protocol performance.
    """
    print("\n" + "=" * 80)
    print("SHARING PATTERN ANALYSIS")
    print("=" * 80)
    
    # Group traces by which protocol performs best
    protocol_wins = {}
    for protocol in df['coherence_scheme'].unique():
        protocol_wins[protocol] = []
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace]
        protocol_avg = trace_df.groupby('coherence_scheme')['ticks'].mean()
        best_protocol = protocol_avg.idxmin()
        protocol_wins[best_protocol].append(trace)
    
    print("\nWorkloads grouped by best-performing protocol:")
    for protocol, traces in sorted(protocol_wins.items()):
        if traces:
            print(f"\n  {protocol} ({len(traces)} workloads):")
            for trace in traces:
                print(f"    - {trace}")
    
    # Analyze what this tells us about sharing patterns
    print("\n" + "-" * 80)
    print("Sharing pattern insights:")
    
    insights = {
        'MI': 'Heavy write sharing or exclusive access (invalidation-based)',
        'MSI': 'Moderate read sharing with occasional writes',
        'MESI': 'Exclusive reads followed by writes (producer-consumer)',
        'MOESI': 'Heavy read sharing with dirty data (multiple readers, one writer)',
        'MESIF': 'Heavy read sharing with clean data (many readers, infrequent writes)'
    }
    
    for protocol, insight in insights.items():
        if protocol in protocol_wins and protocol_wins[protocol]:
            print(f"\n  {protocol} works best when: {insight}")
            print(f"    (Applies to {len(protocol_wins[protocol])} workload(s))")

def analyze_processor_protocol_interaction(df):
    """Analyze interaction between processor count and protocol choice."""
    print("\n" + "=" * 80)
    print("PROCESSOR COUNT × PROTOCOL INTERACTION")
    print("=" * 80)
    
    # Pivot table: processor count vs protocol
    interaction = df.pivot_table(
        index='processor_count',
        columns='coherence_scheme',
        values='ticks',
        aggfunc='mean'
    ).round(0)
    
    print("\nAverage ticks by processor count and protocol:")
    print(interaction.to_string())
    
    # Analyze which protocol is best for each processor count
    print("\n" + "-" * 80)
    print("Best protocol by processor count:")
    for proc_count in sorted(df['processor_count'].unique()):
        proc_df = df[df['processor_count'] == proc_count]
        protocol_avg = proc_df.groupby('coherence_scheme')['ticks'].mean()
        best_protocol = protocol_avg.idxmin()
        best_ticks = protocol_avg.min()
        
        print(f"\n  {proc_count} processors:")
        print(f"    Best: {best_protocol} ({best_ticks:,.0f} ticks)")
        
        # Show top 3
        top3 = protocol_avg.nsmallest(3)
        print(f"    Top 3:")
        for i, (proto, ticks) in enumerate(top3.items(), 1):
            print(f"      {i}. {proto}: {ticks:,.0f} ticks")
    
    return interaction

def generate_summary_report(df):
    """Generate comprehensive summary report."""
    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY")
    print("=" * 80)
    
    # Overall best configuration
    best_idx = df['ticks'].idxmin()
    best = df.loc[best_idx]
    
    print("\n1. BEST OVERALL CONFIGURATION:")
    print(f"   Protocol: {best['coherence_scheme']}")
    print(f"   Processors: {best['processor_count']}")
    print(f"   Workload: {best['trace']}")
    print(f"   Ticks: {best['ticks']:,.0f}")
    print(f"   Time: {best['real_time']:.2f}s")
    
    # Performance range
    print("\n2. PERFORMANCE RANGE:")
    print(f"   Ticks range: {df['ticks'].min():,.0f} - {df['ticks'].max():,.0f}")
    print(f"   Average: {df['ticks'].mean():,.0f} ± {df['ticks'].std():,.0f}")
    
    # Protocol comparison
    print("\n3. PROTOCOL RANKING (by average ticks):")
    protocol_avg = df.groupby('coherence_scheme')['ticks'].mean().sort_values()
    for rank, (protocol, ticks) in enumerate(protocol_avg.items(), 1):
        print(f"   {rank}. {protocol}: {ticks:,.0f} ticks")
    
    # Key findings
    print("\n4. KEY FINDINGS:")
    
    # Best protocol
    best_protocol = protocol_avg.index[0]
    worst_protocol = protocol_avg.index[-1]
    improvement = ((protocol_avg[worst_protocol] - protocol_avg[best_protocol]) / 
                  protocol_avg[worst_protocol]) * 100
    print(f"   • {best_protocol} outperforms {worst_protocol} by {improvement:.1f}%")
    
    # Processor scaling
    proc_counts = sorted(df['processor_count'].unique())
    if len(proc_counts) > 1:
        scaling_2p = df[df['processor_count'] == proc_counts[0]]['ticks'].mean()
        scaling_max = df[df['processor_count'] == proc_counts[-1]]['ticks'].mean()
        scaling_overhead = ((scaling_max - scaling_2p) / scaling_2p) * 100
        print(f"   • Scaling from {proc_counts[0]} to {proc_counts[-1]} processors: "
              f"{scaling_overhead:+.1f}% overhead")
    
    # Workload variation
    trace_variation = df.groupby('trace')['ticks'].mean()
    max_variation = ((trace_variation.max() - trace_variation.min()) / 
                    trace_variation.min()) * 100
    print(f"   • Workload variation: up to {max_variation:.1f}% difference between traces")
    
    # State benefits summary
    if 'MI' in protocol_avg.index and 'MESI' in protocol_avg.index:
        mi_to_mesi = ((protocol_avg['MI'] - protocol_avg['MESI']) / protocol_avg['MI']) * 100
        print(f"   • Adding S and E states (MI→MESI): {mi_to_mesi:.1f}% improvement")
    
    print("\n5. RECOMMENDATIONS:")
    
    # General recommendation
    print(f"   • For general use: {best_protocol} protocol provides best average performance")
    
    # Processor-specific recommendations
    for proc_count in sorted(df['processor_count'].unique()):
        proc_df = df[df['processor_count'] == proc_count]
        best_for_proc = proc_df.groupby('coherence_scheme')['ticks'].mean().idxmin()
        print(f"   • For {proc_count} processors: {best_for_proc} protocol recommended")
    
    # Workload-specific insights
    print(f"   • Protocol choice can impact performance by up to {improvement:.1f}%")
    print(f"   • Consider workload sharing patterns when selecting protocol")

def create_visualizations(df, output_dir):
    """Create comprehensive visualizations."""
    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATIONS")
    print("=" * 80)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set style
    sns.set_style("whitegrid")
    sns.set_palette("husl")
    
    # 1. Protocol Performance Comparison
    fig, ax = plt.subplots(figsize=(12, 6))
    protocol_perf = df.groupby('coherence_scheme')['ticks'].mean().sort_values()
    protocol_perf.plot(kind='bar', ax=ax, color='steelblue')
    ax.set_ylabel('Average Ticks')
    ax.set_xlabel('Coherence Protocol')
    ax.set_title('Coherence Protocol Performance Comparison')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'protocol_comparison.png', dpi=300, bbox_inches='tight')
    print("  ✓ Saved: protocol_comparison.png")
    plt.close()
    
    # 2. Scaling Analysis
    fig, ax = plt.subplots(figsize=(12, 7))
    for protocol in sorted(df['coherence_scheme'].unique()):
        protocol_df = df[df['coherence_scheme'] == protocol]
        scaling = protocol_df.groupby('processor_count')['ticks'].mean()
        ax.plot(scaling.index, scaling.values, marker='o', linewidth=2, 
                markersize=8, label=protocol)
    
    ax.set_xlabel('Number of Processors')
    ax.set_ylabel('Average Ticks')
    ax.set_title('Protocol Scaling with Processor Count')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'scaling_analysis.png', dpi=300, bbox_inches='tight')
    print("  ✓ Saved: scaling_analysis.png")
    plt.close()
    
    # 3. Workload Performance Heatmap
    workload_pivot = df.pivot_table(
        index='trace',
        columns='coherence_scheme',
        values='ticks',
        aggfunc='mean'
    )
    
    # Normalize by row to show relative performance
    workload_normalized = workload_pivot.div(workload_pivot.min(axis=1), axis=0)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Absolute values
    sns.heatmap(workload_pivot, annot=True, fmt='.0f', cmap='YlOrRd', 
                ax=ax1, cbar_kws={'label': 'Ticks'})
    ax1.set_title('Workload Performance by Protocol (Absolute Ticks)')
    ax1.set_xlabel('Coherence Protocol')
    ax1.set_ylabel('Workload')
    
    # Normalized values
    sns.heatmap(workload_normalized, annot=True, fmt='.2f', cmap='RdYlGn_r',
                ax=ax2, cbar_kws={'label': 'Relative Performance'}, center=1.0)
    ax2.set_title('Workload Performance by Protocol (Normalized to Best)')
    ax2.set_xlabel('Coherence Protocol')
    ax2.set_ylabel('Workload')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'workload_heatmap.png', dpi=300, bbox_inches='tight')
    print("  ✓ Saved: workload_heatmap.png")
    plt.close()
    
    # 4. Processor × Protocol Interaction
    interaction_pivot = df.pivot_table(
        index='processor_count',
        columns='coherence_scheme',
        values='ticks',
        aggfunc='mean'
    )
    
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(interaction_pivot, annot=True, fmt='.0f', cmap='coolwarm',
                ax=ax, cbar_kws={'label': 'Average Ticks'})
    ax.set_title('Processor Count × Protocol Interaction')
    ax.set_xlabel('Coherence Protocol')
    ax.set_ylabel('Number of Processors')
    plt.tight_layout()
    plt.savefig(output_dir / 'processor_protocol_interaction.png', dpi=300, bbox_inches='tight')
    print("  ✓ Saved: processor_protocol_interaction.png")
    plt.close()
    
    # 5. Box plot showing distribution
    fig, ax = plt.subplots(figsize=(12, 6))
    df_sorted = df.sort_values('coherence_scheme')
    sns.boxplot(data=df_sorted, x='coherence_scheme', y='ticks', ax=ax)
    ax.set_ylabel('Ticks')
    ax.set_xlabel('Coherence Protocol')
    ax.set_title('Performance Distribution by Protocol')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'performance_distribution.png', dpi=300, bbox_inches='tight')
    print("  ✓ Saved: performance_distribution.png")
    plt.close()
    
    # 6. State benefit visualization
    protocol_order = ['MI', 'MSI', 'MESI', 'MOESI', 'MESIF']
    available_protocols = [p for p in protocol_order if p in df['coherence_scheme'].unique()]
    
    if len(available_protocols) > 1:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        protocol_avg = df.groupby('coherence_scheme')['ticks'].mean()
        protocol_std = df.groupby('coherence_scheme')['ticks'].std()
        
        x_pos = range(len(available_protocols))
        values = [protocol_avg[p] for p in available_protocols]
        errors = [protocol_std[p] for p in available_protocols]
        
        bars = ax.bar(x_pos, values, yerr=errors, capsize=5, 
                     color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'][:len(available_protocols)])
        
        # Add percentage labels showing improvement over MI
        if 'MI' in available_protocols:
            mi_value = protocol_avg['MI']
            for i, (p, v) in enumerate(zip(available_protocols, values)):
                if p != 'MI':
                    improvement = ((mi_value - v) / mi_value) * 100
                    ax.text(i, v, f'{improvement:+.1f}%', ha='center', va='bottom', fontweight='bold')
        
        ax.set_xticks(x_pos)
        ax.set_xticklabels(available_protocols)
        ax.set_ylabel('Average Ticks')
        ax.set_xlabel('Coherence Protocol')
        ax.set_title('Incremental Benefit of Additional Coherence States')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
        plt.tight_layout()
        plt.savefig(output_dir / 'state_benefits.png', dpi=300, bbox_inches='tight')
        print("  ✓ Saved: state_benefits.png")
        plt.close()
    
    print(f"\n  All visualizations saved to: {output_dir}")

def main():
    """Main analysis function."""
    results_file = Path("experiments_P5/experiment_results/coherence_results.csv")
    
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        print("Please run coherence_experiment.py first.")
        return
    
    print("Loading experiment results...")
    df = load_results(results_file)
    
    if len(df) == 0:
        print("Error: No valid results found in the CSV file.")
        return
    
    print(f"Loaded {len(df)} successful simulation results")
    print(f"Protocols tested: {sorted(df['coherence_scheme'].unique())}")
    print(f"Processor counts: {sorted(df['processor_count'].unique())}")
    print(f"Workloads: {df['trace'].nunique()}")
    
    # Run analyses
    analyze_protocol_performance(df)
    analyze_state_benefits(df)
    analyze_processor_scaling(df)
    analyze_workload_sensitivity(df)
    analyze_sharing_patterns(df)
    analyze_processor_protocol_interaction(df)
    generate_summary_report(df)
    
    # Generate visualizations
    try:
        create_visualizations(df, "experiments_P5/experiment_results/figures")
    except Exception as e:
        print(f"\nWarning: Could not generate all visualizations: {e}")
        print("(matplotlib/seaborn may need to be installed: pip install matplotlib seaborn)")
    
    # Save summary to file
    output_file = Path("experiments_P5/experiment_results/coherence_analysis_report.txt")
    print(f"\n" + "=" * 80)
    print(f"Analysis complete! Summary saved to: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
