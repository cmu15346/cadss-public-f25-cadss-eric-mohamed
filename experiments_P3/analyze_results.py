#!/usr/bin/env python3
"""
P3 Integration Results Analysis Script

This script analyzes the results from the integration experiments to answer:
1. How does the superscalar pipeline handle cache misses and branch mispredictions?
2. What resources ameliorate the impact of these stalls?
3. What are the tradeoffs between different components?
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

def load_results(csv_file):
    """Load experiment results from CSV."""
    df = pd.read_csv(csv_file)
    
    # Filter out failed simulations
    df = df[df['simulation_success'] == True]
    
    # Calculate IPC (Instructions Per Cycle)
    df['ipc'] = df['total_instructions'] / df['ticks']
    
    return df

def analyze_cache_impact(df):
    """Analyze how cache configuration affects performance."""
    print("=" * 80)
    print("CACHE CONFIGURATION IMPACT")
    print("=" * 80)
    
    # Group by cache type and calculate average performance
    cache_perf = df.groupby(['cache_type', 'cache_size']).agg({
        'ticks': 'mean',
        'aat': 'mean',
        'ipc': 'mean'
    }).round(2)
    
    print("\nAverage performance by cache configuration:")
    print(cache_perf.to_string())
    
    # Find best cache config
    best_cache = cache_perf.sort_values('ipc', ascending=False).head(1)
    print(f"\nBest cache configuration:")
    print(best_cache.to_string())
    
    return cache_perf

def analyze_branch_impact(df):
    """Analyze how branch predictor configuration affects performance."""
    print("\n" + "=" * 80)
    print("BRANCH PREDICTOR IMPACT")
    print("=" * 80)
    
    # Group by branch type and calculate average performance
    branch_perf = df.groupby(['branch_type', 'branch_counters']).agg({
        'ticks': 'mean',
        'aat': 'mean',
        'ipc': 'mean'
    }).round(2)
    
    print("\nAverage performance by branch predictor configuration:")
    print(branch_perf.to_string())
    
    # Find best branch config
    best_branch = branch_perf.sort_values('ipc', ascending=False).head(1)
    print(f"\nBest branch predictor configuration:")
    print(best_branch.to_string())
    
    return branch_perf

def analyze_processor_impact(df):
    """Analyze how processor pipeline configuration affects performance."""
    print("\n" + "=" * 80)
    print("PROCESSOR PIPELINE IMPACT")
    print("=" * 80)
    
    # Group by processor type and calculate average performance
    proc_perf = df.groupby('proc_type').agg({
        'ticks': 'mean',
        'aat': 'mean',
        'ipc': 'mean',
        'fetch_rate': 'first',
        'dispatch_mult': 'first',
        'schedule_mult': 'first',
        'fast_alu': 'first',
        'long_alu': 'first',
        'num_cdb': 'first'
    }).round(2)
    
    print("\nAverage performance by processor configuration:")
    print(proc_perf.to_string())
    
    # Find best processor config
    best_proc = proc_perf.sort_values('ipc', ascending=False).head(1)
    print(f"\nBest processor configuration:")
    print(best_proc.to_string())
    
    return proc_perf

def analyze_resource_impact(df):
    """
    Analyze which processor resources help ameliorate cache/branch stalls.
    """
    print("\n" + "=" * 80)
    print("RESOURCE IMPACT ON STALL AMELIORATION")
    print("=" * 80)
    
    # Compare baseline to other configurations
    baseline = df[df['proc_type'] == 'Baseline']['ipc'].mean()
    
    resource_impact = []
    for proc_type in df['proc_type'].unique():
        if proc_type == 'Baseline':
            continue
        
        ipc = df[df['proc_type'] == proc_type]['ipc'].mean()
        improvement = ((ipc - baseline) / baseline) * 100
        
        resource_impact.append({
            'Configuration': proc_type,
            'Average IPC': round(ipc, 3),
            'Improvement vs Baseline': f"{improvement:.1f}%"
        })
    
    resource_df = pd.DataFrame(resource_impact).sort_values('Average IPC', ascending=False)
    
    print("\nProcessor resource impact (sorted by IPC improvement):")
    print(resource_df.to_string(index=False))
    
    # Analyze specific resource effects
    print("\n--- Resource-specific analysis ---")
    
    # Fetch rate impact
    fetch_impact = df.groupby('fetch_rate')['ipc'].mean().sort_index()
    print(f"\nFetch rate impact on IPC:")
    for fetch, ipc in fetch_impact.items():
        improvement = ((ipc - fetch_impact.iloc[0]) / fetch_impact.iloc[0]) * 100
        print(f"  f={fetch}: IPC={ipc:.3f} ({improvement:+.1f}%)")
    
    # Number of FUs impact
    df['total_fus'] = df['fast_alu'] + df['long_alu']
    fu_impact = df.groupby('total_fus')['ipc'].mean().sort_index()
    print(f"\nTotal functional units impact on IPC:")
    for fus, ipc in fu_impact.items():
        improvement = ((ipc - fu_impact.iloc[0]) / fu_impact.iloc[0]) * 100
        print(f"  FUs={fus}: IPC={ipc:.3f} ({improvement:+.1f}%)")
    
    # Schedule multiplier (RS size) impact
    schedule_impact = df.groupby('schedule_mult')['ipc'].mean().sort_index()
    print(f"\nReservation station size (schedule_mult) impact on IPC:")
    for m, ipc in schedule_impact.items():
        improvement = ((ipc - schedule_impact.iloc[0]) / schedule_impact.iloc[0]) * 100
        print(f"  m={m}: IPC={ipc:.3f} ({improvement:+.1f}%)")
    
    return resource_df

def analyze_interactions(df):
    """
    Analyze interactions between cache and branch predictor configurations.
    """
    print("\n" + "=" * 80)
    print("CACHE-BRANCH PREDICTOR INTERACTIONS")
    print("=" * 80)
    
    # Create interaction matrix for best processor config
    best_proc = df.groupby('proc_type')['ipc'].mean().idxmax()
    df_best_proc = df[df['proc_type'] == best_proc]
    
    print(f"\nAnalyzing interactions with {best_proc} processor configuration:")
    
    # Pivot table: cache vs branch configurations
    interaction = df_best_proc.pivot_table(
        index='cache_type',
        columns='branch_type',
        values='ipc',
        aggfunc='mean'
    ).round(3)
    
    print("\nIPC matrix (rows=cache, columns=branch):")
    print(interaction.to_string())
    
    # Find best combination
    best_combo_idx = df_best_proc.groupby(['cache_type', 'branch_type'])['ipc'].mean().idxmax()
    best_combo_ipc = df_best_proc.groupby(['cache_type', 'branch_type'])['ipc'].mean().max()
    
    print(f"\nBest cache-branch combination:")
    print(f"  Cache: {best_combo_idx[0]}")
    print(f"  Branch: {best_combo_idx[1]}")
    print(f"  IPC: {best_combo_ipc:.3f}")
    
    return interaction

def analyze_tradeoffs(df):
    """
    Analyze tradeoffs between different component configurations.
    """
    print("\n" + "=" * 80)
    print("DESIGN TRADEOFFS")
    print("=" * 80)
    
    # Cache size vs performance
    print("\n1. Cache Size vs Performance:")
    cache_tradeoff = df.groupby('cache_size').agg({
        'ipc': 'mean',
        'ticks': 'mean'
    }).round(3)
    cache_tradeoff['cache_size_kb'] = cache_tradeoff.index / 1024
    print(cache_tradeoff[['cache_size_kb', 'ipc', 'ticks']].to_string())
    
    # Branch predictor counters vs performance
    print("\n2. Branch Predictor Size vs Performance:")
    branch_tradeoff = df.groupby('branch_counters').agg({
        'ipc': 'mean',
        'ticks': 'mean'
    }).round(3)
    print(branch_tradeoff.to_string())
    
    # Processor complexity vs performance
    print("\n3. Processor Complexity vs Performance:")
    # Define complexity metric as sum of resources
    df['proc_complexity'] = (df['fetch_rate'] + df['dispatch_mult'] + 
                             df['schedule_mult'] + df['fast_alu'] + 
                             df['long_alu'] + df['num_cdb'])
    
    proc_tradeoff = df.groupby('proc_type').agg({
        'proc_complexity': 'first',
        'ipc': 'mean',
        'ticks': 'mean'
    }).round(3).sort_values('proc_complexity')
    
    print(proc_tradeoff.to_string())
    
    # Calculate efficiency (IPC per unit complexity)
    proc_tradeoff['efficiency'] = proc_tradeoff['ipc'] / proc_tradeoff['proc_complexity']
    print("\n4. Processor Efficiency (IPC per unit complexity):")
    print(proc_tradeoff[['proc_complexity', 'ipc', 'efficiency']].sort_values('efficiency', ascending=False).to_string())

def analyze_by_trace(df):
    """
    Analyze performance characteristics by trace file.
    """
    print("\n" + "=" * 80)
    print("PERFORMANCE BY WORKLOAD (TRACE)")
    print("=" * 80)
    
    trace_perf = df.groupby('trace').agg({
        'ticks': 'mean',
        'aat': 'mean',
        'ipc': 'mean',
        'total_instructions': 'first'
    }).round(3)
    
    print("\nAverage performance by trace:")
    print(trace_perf.to_string())
    
    # Find which configurations work best for each trace
    print("\n--- Best configurations per trace ---")
    for trace in df['trace'].unique():
        df_trace = df[df['trace'] == trace]
        best_idx = df_trace['ipc'].idxmax()
        best_row = df_trace.loc[best_idx]
        
        print(f"\n{trace}:")
        print(f"  Best IPC: {best_row['ipc']:.3f}")
        print(f"  Processor: {best_row['proc_type']}")
        print(f"  Cache: {best_row['cache_type']}")
        print(f"  Branch: {best_row['branch_type']}")

def generate_summary_report(df):
    """
    Generate a comprehensive summary report.
    """
    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY")
    print("=" * 80)
    
    # Overall best configuration
    best_idx = df['ipc'].idxmax()
    best = df.loc[best_idx]
    
    print("\n1. BEST OVERALL CONFIGURATION:")
    print(f"   IPC: {best['ipc']:.3f}")
    print(f"   Ticks: {best['ticks']:,}")
    print(f"   AAT: {best['aat']:.2f}")
    print(f"   Trace: {best['trace']}")
    print(f"   Processor: {best['proc_type']} (f={best['fetch_rate']}, d={best['dispatch_mult']}, " +
          f"m={best['schedule_mult']}, j={best['fast_alu']}, k={best['long_alu']}, c={best['num_cdb']})")
    print(f"   Cache: {best['cache_type']} (s={best['cache_s']}, E={best['cache_E']}, " +
          f"b={best['cache_b']}, size={best['cache_size']/1024:.1f}KB)")
    print(f"   Branch: {best['branch_type']} (s={best['branch_s']}, b={best['branch_b']}, " +
          f"g={best['branch_g']}, counters={best['branch_counters']})")
    
    # Performance range
    print("\n2. PERFORMANCE RANGE:")
    print(f"   IPC range: {df['ipc'].min():.3f} - {df['ipc'].max():.3f}")
    print(f"   AAT range: {df['aat'].min():.2f} - {df['aat'].max():.2f}")
    print(f"   Ticks range: {df['ticks'].min():,} - {df['ticks'].max():,}")
    
    # Key findings
    print("\n3. KEY FINDINGS:")
    
    # Cache impact
    cache_impact = df.groupby('cache_type')['ipc'].mean()
    best_cache = cache_impact.idxmax()
    worst_cache = cache_impact.idxmin()
    cache_improvement = ((cache_impact[best_cache] - cache_impact[worst_cache]) / cache_impact[worst_cache]) * 100
    print(f"   • Cache: {best_cache} outperforms {worst_cache} by {cache_improvement:.1f}%")
    
    # Branch impact
    branch_impact = df.groupby('branch_type')['ipc'].mean()
    best_branch = branch_impact.idxmax()
    worst_branch = branch_impact.idxmin()
    branch_improvement = ((branch_impact[best_branch] - branch_impact[worst_branch]) / branch_impact[worst_branch]) * 100
    print(f"   • Branch: {best_branch} outperforms {worst_branch} by {branch_improvement:.1f}%")
    
    # Processor impact
    proc_impact = df.groupby('proc_type')['ipc'].mean()
    best_proc = proc_impact.idxmax()
    worst_proc = proc_impact.idxmin()
    proc_improvement = ((proc_impact[best_proc] - proc_impact[worst_proc]) / proc_impact[worst_proc]) * 100
    print(f"   • Processor: {best_proc} outperforms {worst_proc} by {proc_improvement:.1f}%")
    
    print("\n4. STALL AMELIORATION:")
    baseline_ipc = df[df['proc_type'] == 'Baseline']['ipc'].mean()
    
    for proc_type in ['More-FUs', 'Large-RS', 'High-End']:
        if proc_type in df['proc_type'].values:
            ipc = df[df['proc_type'] == proc_type]['ipc'].mean()
            improvement = ((ipc - baseline_ipc) / baseline_ipc) * 100
            print(f"   • {proc_type}: {improvement:+.1f}% vs Baseline")

def create_visualizations(df, output_dir):
    """
    Create visualization plots for the results.
    """
    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATIONS")
    print("=" * 80)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Set style
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    
    # 1. Processor configuration comparison
    fig, ax = plt.subplots()
    proc_perf = df.groupby('proc_type')['ipc'].mean().sort_values(ascending=True)
    proc_perf.plot(kind='barh', ax=ax, color='steelblue')
    ax.set_xlabel('Average IPC')
    ax.set_ylabel('Processor Configuration')
    ax.set_title('Processor Configuration Impact on IPC')
    plt.tight_layout()
    plt.savefig(output_dir / 'processor_impact.png', dpi=300)
    print(f"  Saved: processor_impact.png")
    plt.close()
    
    # 2. Cache configuration comparison
    fig, ax = plt.subplots()
    cache_perf = df.groupby('cache_type')['ipc'].mean().sort_values(ascending=True)
    cache_perf.plot(kind='barh', ax=ax, color='coral')
    ax.set_xlabel('Average IPC')
    ax.set_ylabel('Cache Configuration')
    ax.set_title('Cache Configuration Impact on IPC')
    plt.tight_layout()
    plt.savefig(output_dir / 'cache_impact.png', dpi=300)
    print(f"  Saved: cache_impact.png")
    plt.close()
    
    # 3. Branch predictor comparison
    fig, ax = plt.subplots()
    branch_perf = df.groupby('branch_type')['ipc'].mean().sort_values(ascending=True)
    branch_perf.plot(kind='barh', ax=ax, color='forestgreen')
    ax.set_xlabel('Average IPC')
    ax.set_ylabel('Branch Predictor Configuration')
    ax.set_title('Branch Predictor Impact on IPC')
    plt.tight_layout()
    plt.savefig(output_dir / 'branch_impact.png', dpi=300)
    print(f"  Saved: branch_impact.png")
    plt.close()
    
    # 4. Cache-Branch interaction heatmap
    best_proc = df.groupby('proc_type')['ipc'].mean().idxmax()
    df_best_proc = df[df['proc_type'] == best_proc]
    
    interaction = df_best_proc.pivot_table(
        index='cache_type',
        columns='branch_type',
        values='ipc',
        aggfunc='mean'
    )
    
    fig, ax = plt.subplots(figsize=(14, 10))
    sns.heatmap(interaction, annot=True, fmt='.3f', cmap='YlGnBu', ax=ax)
    ax.set_title(f'Cache-Branch Predictor Interaction (IPC)\nProcessor: {best_proc}')
    ax.set_xlabel('Branch Predictor Configuration')
    ax.set_ylabel('Cache Configuration')
    plt.tight_layout()
    plt.savefig(output_dir / 'interaction_heatmap.png', dpi=300)
    print(f"  Saved: interaction_heatmap.png")
    plt.close()
    
    # 5. Trace comparison
    fig, ax = plt.subplots()
    trace_perf = df.groupby('trace')['ipc'].mean().sort_values(ascending=True)
    trace_perf.plot(kind='barh', ax=ax, color='mediumpurple')
    ax.set_xlabel('Average IPC')
    ax.set_ylabel('Trace')
    ax.set_title('Performance by Workload')
    plt.tight_layout()
    plt.savefig(output_dir / 'trace_comparison.png', dpi=300)
    print(f"  Saved: trace_comparison.png")
    plt.close()
    
    print(f"\nAll visualizations saved to: {output_dir}")

def main():
    """Main analysis function."""
    # Load results
    results_file = Path("experiments_P3/experiment_results/integration_results.csv")
    
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        print("Please run integration_experiment.py first.")
        return
    
    print("Loading results...")
    df = load_results(results_file)
    
    print(f"Loaded {len(df)} successful experiments")
    print(f"Experiments: {df['exp_id'].nunique()} configurations × {df['trace'].nunique()} traces")
    
    # Run analyses
    analyze_processor_impact(df)
    analyze_cache_impact(df)
    analyze_branch_impact(df)
    analyze_resource_impact(df)
    analyze_interactions(df)
    analyze_tradeoffs(df)
    analyze_by_trace(df)
    generate_summary_report(df)
    
    # Generate visualizations
    try:
        create_visualizations(df, "experiments_P3/experiment_results/figures")
    except Exception as e:
        print(f"\nNote: Could not generate visualizations: {e}")
        print("(matplotlib/seaborn may not be installed)")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
