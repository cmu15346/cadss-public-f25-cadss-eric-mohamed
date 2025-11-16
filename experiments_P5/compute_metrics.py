#!/usr/bin/env python3
import pandas as pd
p='experiments_P5/experiment_results/coherence_results.csv'
df=pd.read_csv(p)
df=df[df['simulation_success']==True]
prot=df.groupby('coherence_scheme')['ticks'].mean()
order=prot.sort_values()
print('protocol_order_mean:')
for k,v in order.items():
    print(f'{k}: {v:.2f}')
mi=prot['MI']
print('\nImprovements over MI:')
for name in ['MOESI','MESIF','MESI','MSI']:
    val=prot[name]
    print(f'{name}: {(mi-val)/mi*100:.2f}%')
# best per trace
trace_best = df.groupby(['trace','coherence_scheme'])['ticks'].mean().unstack()
for trace in trace_best.index:
    best=trace_best.loc[trace].idxmin()
    bval=trace_best.loc[trace].min()
    wval=trace_best.loc[trace].max()
    print(f'\nTrace {trace}: best={best} (ticks={bval:.0f}), worst_ticks={wval:.0f}, range_pct={(wval-bval)/wval*100:.2f}%')
# scaling
scaling = df.groupby(['coherence_scheme','processor_count'])['ticks'].mean().unstack()
print('\nScaling (mean ticks):')
print(scaling.to_string())
