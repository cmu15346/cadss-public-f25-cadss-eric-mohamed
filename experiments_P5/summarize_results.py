#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
p = Path('experiments_P5/experiment_results/coherence_results.csv')
if not p.exists():
    print('CSV not found')
    raise SystemExit(1)

df = pd.read_csv(p)
# Keep successful
df = df[df['simulation_success'] == True]
# ensure types
df['ticks'] = pd.to_numeric(df['ticks'], errors='coerce')
# per protocol
prot = df.groupby('coherence_scheme')['ticks'].agg(['mean','std','min','max','count']).sort_values('mean')
# per trace best
trace_best = df.groupby(['trace','coherence_scheme'])['ticks'].mean().unstack()
best_per_trace = trace_best.idxmin(axis=1).to_frame('best_protocol')
best_per_trace['best_ticks'] = trace_best.min(axis=1)
worst_per_trace = trace_best.max(axis=1)
best_per_trace['worst_ticks'] = worst_per_trace
best_per_trace['range_pct'] = (best_per_trace['worst_ticks']-best_per_trace['best_ticks'])/best_per_trace['worst_ticks']*100
# protocol scaling
scaling = df.groupby(['coherence_scheme','processor_count'])['ticks'].mean().unstack()

out = Path('experiments_P5/experiment_results/summary.txt')
with out.open('w') as f:
    f.write('Protocol summary (mean ticks):\n')
    f.write(prot.to_string())
    f.write('\n\nBest protocol per trace:\n')
    f.write(best_per_trace.to_string())
    f.write('\n\nScaling (mean ticks by processor count):\n')
    f.write(scaling.to_string())

print('WROTE', out)
print('\n---PROTOCOL SUMMARY---')
print(prot)
print('\n---BEST PER TRACE---')
print(best_per_trace)
print('\n---SCALING---')
print(scaling)
