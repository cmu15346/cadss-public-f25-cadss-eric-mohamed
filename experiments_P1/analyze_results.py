#!/usr/bin/env python3
"""
Cache Experiment Analysis Script

This script analyzes the results from cache_experiment.py to find
the optimal cache configuration with the lowest AAT.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def load_and_clean_results(csv_file):
    """Load and clean the experiment results."""
    df = pd.read_csv(csv_file)
    
    # Filter successful simulations only
    df = df[df['simulation_success'] == True].copy()
    
    # Convert numeric columns
    numeric_cols = ['s', 'E', 'b', 'r', 'i', 'size_bytes', 'total_accesses', 'ticks', 'aat']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remove rows with invalid data
    df = df.dropna(subset=['aat'])
    df = df[df['aat'] > 0]
    
    return df

def analyze_by_trace(df):
    """Analyze results for each trace separately."""
    results = {}
    
    for trace in df['trace'].unique():
        trace_df = df[df['trace'] == trace].copy()
        
        if len(trace_df) == 0:
            continue
            
        # Find configuration with lowest AAT
        best_config = trace_df.loc[trace_df['aat'].idxmin()]
        
        # Calculate statistics
        stats = {
            'trace': trace,
            'num_configs': len(trace_df),
            'best_config_id': best_config['config_id'],
            'best_aat': best_config['aat'],
            'best_type': best_config['type'],
            'best_s': best_config['s'],
            'best_E': best_config['E'],
            'best_b': best_config['b'],
            'best_r': best_config['r'],
            'best_i': best_config['i'],
            'best_size': best_config['size_bytes'],
            'best_ticks': best_config.get('ticks', 0),
            'best_accesses': best_config.get('total_accesses', 0),
            'mean_aat': trace_df['aat'].mean(),
            'std_aat': trace_df['aat'].std(),
            'min_aat': trace_df['aat'].min(),
            'max_aat': trace_df['aat'].max()
        }
        
        results[trace] = stats
    
    return results

def find_universal_config(df):
    """Find the configuration that performs best across all traces."""
    
    # Calculate mean AAT for each configuration across all traces
    config_performance = df.groupby('config_id').agg({
        'aat': ['mean', 'std', 'min', 'max'],
        'trace': 'count',
        'type': 'first',
        's': 'first',
        'E': 'first', 
        'b': 'first',
        'r': 'first',
        'i': 'first',
        'size_bytes': 'first'
    }).round(4)
    
    # Flatten column names
    config_performance.columns = ['_'.join(col).strip() for col in config_performance.columns]
    
    # Only consider configurations tested on all traces
    num_traces = df['trace'].nunique()
    config_performance = config_performance[config_performance['trace_count'] == num_traces]
    
    if len(config_performance) == 0:
        print("Warning: No configuration was tested on all traces")
        return None
    
    # Find configuration with lowest mean AAT
    best_config_id = config_performance['aat_mean'].idxmin()
    best_config = config_performance.loc[best_config_id]
    
    return best_config_id, best_config

def create_visualizations(df, output_dir):
    """Create visualizations of the results."""
    
    plt.style.use('default')
    fig_dir = Path(output_dir) / "figures"
    fig_dir.mkdir(exist_ok=True)
    
    # 1. AAT distribution by cache type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x='type', y='aat')
    plt.title('Average Access Time (AAT) Distribution by Cache Type')
    plt.ylabel('Average Access Time (cycles per access)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(fig_dir / "aat_by_type.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. AAT vs Cache Size
    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(df['size_bytes']/1024, df['aat'], 
                         c=df.index, cmap='viridis', alpha=0.6)
    plt.colorbar(scatter, label='Configuration Index')
    plt.xlabel('Cache Size (KB)')
    plt.ylabel('Average Access Time (cycles per access)')
    plt.title('Cache Size vs AAT')
    plt.tight_layout()
    plt.savefig(fig_dir / "size_vs_aat.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Heatmap of AAT by parameters (for LRU configs)
    lru_df = df[df['type'] == 'LRU'].copy()
    if len(lru_df) > 0:
        pivot_table = lru_df.pivot_table(values='aat', index='s', columns='E', aggfunc='mean')
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(pivot_table, annot=True, fmt='.2f', cmap='RdYlBu_r')
        plt.title('Average Access Time by Set Bits (s) and Associativity (E) - LRU Only')
        plt.tight_layout()
        plt.savefig(fig_dir / "lru_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # 3b. Heatmap for RRIP configurations
    rrip_df = df[df['type'].str.contains('RRIP')].copy()
    if len(rrip_df) > 0:
        pivot_table = rrip_df.pivot_table(values='aat', index='s', columns='E', aggfunc='mean')
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(pivot_table, annot=True, fmt='.2f', cmap='RdYlBu_r')
        plt.title('Average Access Time by Set Bits (s) and Associativity (E) - RRIP Configurations')
        plt.tight_layout()
        plt.savefig(fig_dir / "rrip_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # 3c. Comparison of cache types
    plt.figure(figsize=(12, 8))
    type_comparison = df.groupby(['type', 's', 'E'])['aat'].mean().reset_index()
    
    for cache_type in df['type'].unique():
        type_data = type_comparison[type_comparison['type'] == cache_type]
        plt.scatter(type_data['s'], type_data['aat'], 
                   label=cache_type, alpha=0.7, s=50)
    
    plt.xlabel('Set Bits (s)')
    plt.ylabel('Average Access Time (cycles per access)')
    plt.title('Cache Performance Comparison by Type and Set Bits')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(fig_dir / "type_comparison.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Performance by trace
    if df['trace'].nunique() > 1:
        plt.figure(figsize=(14, 6))
        trace_stats = df.groupby('trace')['aat'].agg(['mean', 'min']).reset_index()
        
        x = range(len(trace_stats))
        plt.bar(x, trace_stats['mean'], alpha=0.7, label='Mean AAT')
        plt.bar(x, trace_stats['min'], alpha=0.7, label='Best AAT')
        
        plt.xlabel('Trace')
        plt.ylabel('Average Access Time (cycles per access)')
        plt.title('Cache Performance by Trace')
        plt.xticks(x, trace_stats['trace'], rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_dir / "performance_by_trace.png", dpi=300, bbox_inches='tight')
        plt.close()

def generate_report(df, trace_results, universal_config, output_dir):
    """Generate a comprehensive analysis report."""
    
    report_file = Path(output_dir) / "analysis_report.txt"
    
    with open(report_file, 'w') as f:
        f.write("CACHE EXPERIMENT ANALYSIS REPORT\n")
        f.write("="*50 + "\n\n")
        
        f.write(f"Total configurations tested: {df['config_id'].nunique()}\n")
        f.write(f"Total traces analyzed: {df['trace'].nunique()}\n")
        f.write(f"Total successful simulations: {len(df)}\n\n")
        
        # Overall statistics
        f.write("OVERALL STATISTICS\n")
        f.write("-" * 20 + "\n")
        f.write(f"Mean AAT across all configs/traces: {df['aat'].mean():.4f} cycles per access\n")
        f.write(f"Best AAT found: {df['aat'].min():.4f} cycles per access\n")
        f.write(f"Worst AAT found: {df['aat'].max():.4f} cycles per access\n")
        f.write(f"Standard deviation: {df['aat'].std():.4f}\n")
        f.write(f"Performance improvement potential: {((df['aat'].max() - df['aat'].min()) / df['aat'].max() * 100):.1f}%\n\n")
        
        # Universal configuration
        if universal_config is not None:
            config_id, config_data = universal_config
            f.write("RECOMMENDED UNIVERSAL CONFIGURATION\n")
            f.write("-" * 35 + "\n")
            f.write(f"Configuration ID: {config_id}\n")
            f.write(f"Cache Type: {config_data['type_first']}\n")
            f.write(f"Set bits (s): {config_data['s_first']}\n")
            f.write(f"Associativity (E): {config_data['E_first']}\n")
            f.write(f"Block bits (b): {config_data['b_first']}\n")
            f.write(f"RRIP bits (r): {config_data['r_first']}\n")
            f.write(f"Victim entries (i): {config_data['i_first']}\n")
            f.write(f"Total size: {config_data['size_bytes_first']} bytes ({config_data['size_bytes_first']/1024:.1f} KB)\n")
            f.write(f"Mean AAT: {config_data['aat_mean']:.4f} cycles per access\n")
            f.write(f"AAT Std Dev: {config_data['aat_std']:.4f}\n\n")
        
        # Configuration type analysis
        f.write("CONFIGURATION TYPE ANALYSIS\n")
        f.write("-" * 28 + "\n")
        type_analysis = df.groupby('type').agg({
            'aat': ['count', 'mean', 'std', 'min'],
            'size_bytes': 'mean'
        }).round(4)
        
        type_analysis.columns = ['_'.join(col).strip() for col in type_analysis.columns]
        
        for cache_type in type_analysis.index:
            data = type_analysis.loc[cache_type]
            f.write(f"\n{cache_type}:\n")
            f.write(f"  Configurations tested: {data['aat_count']}\n")
            f.write(f"  Mean AAT: {data['aat_mean']:.4f} cycles per access\n")
            f.write(f"  Best AAT: {data['aat_min']:.4f} cycles per access\n")
            f.write(f"  AAT Std Dev: {data['aat_std']:.4f}\n")
            f.write(f"  Average Size: {data['size_bytes_mean']/1024:.1f} KB\n")
        
        # Per-trace results
        f.write("BEST CONFIGURATION PER TRACE\n")
        f.write("-" * 30 + "\n")
        for trace, stats in trace_results.items():
            f.write(f"\nTrace: {trace}\n")
            f.write(f"  Best Config ID: {stats['best_config_id']}\n")
            f.write(f"  Best AAT: {stats['best_aat']:.4f} cycles per access\n")
            f.write(f"  Total Ticks: {stats['best_ticks']}\n")
            f.write(f"  Total Accesses: {stats['best_accesses']}\n")
            f.write(f"  Configuration: {stats['best_type']} ")
            f.write(f"s={stats['best_s']} E={stats['best_E']} b={stats['best_b']} ")
            f.write(f"r={stats['best_r']} i={stats['best_i']}\n")
            f.write(f"  Size: {stats['best_size']} bytes ({stats['best_size']/1024:.1f} KB)\n")
        
        # Size utilization analysis
        f.write(f"\n\nSIZE UTILIZATION ANALYSIS\n")
        f.write("-" * 25 + "\n")
        f.write(f"Budget: 54 KB (55296 bytes)\n")
        f.write(f"Largest config tested: {df['size_bytes'].max()} bytes ({df['size_bytes'].max()/1024:.1f} KB)\n")
        f.write(f"Average config size: {df['size_bytes'].mean():.0f} bytes ({df['size_bytes'].mean()/1024:.1f} KB)\n")
        f.write(f"Budget utilization: {df['size_bytes'].max()/55296*100:.1f}%\n")

def main():
    """Main analysis function."""
    
    results_file = Path("experiment_results/cache_experiment_results.csv")
    
    if not results_file.exists():
        print(f"Error: Results file {results_file} not found.")
        print("Please run cache_experiment.py first.")
        return
    
    print("Loading experiment results...")
    df = load_and_clean_results(results_file)
    
    if len(df) == 0:
        print("Error: No valid results found in the CSV file.")
        return
    
    print(f"Loaded {len(df)} successful simulation results")
    print(f"Covering {df['config_id'].nunique()} configurations and {df['trace'].nunique()} traces")
    
    # Analyze results
    print("\nAnalyzing results by trace...")
    trace_results = analyze_by_trace(df)
    
    print("Finding universal configuration...")
    universal_config = find_universal_config(df)
    
    # Create output directory
    output_dir = Path("experiment_results")
    
    print("Creating visualizations...")
    create_visualizations(df, output_dir)
    
    print("Generating analysis report...")
    generate_report(df, trace_results, universal_config, output_dir)
    
    # Print summary to console
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)
    
    if universal_config is not None:
        config_id, config_data = universal_config
        print(f"\nRECOMMENDED CONFIGURATION:")
        print(f"  Type: {config_data['type_first']}")
        print(f"  Parameters: s={config_data['s_first']} E={config_data['E_first']} "
              f"b={config_data['b_first']} r={config_data['r_first']} i={config_data['i_first']}")
        print(f"  Size: {config_data['size_bytes_first']/1024:.1f} KB")
        print(f"  Mean AAT: {config_data['aat_mean']:.4f} cycles per access")
    
    print(f"\nDetailed analysis saved to: experiment_results/analysis_report.txt")
    print(f"Visualizations saved to: experiment_results/figures/")

if __name__ == "__main__":
    main()