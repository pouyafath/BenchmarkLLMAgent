import json
import glob
from pathlib import Path

def get_traj_cost(traj_path):
    try:
        with open(traj_path, 'r') as f:
            data = json.load(f)
        
        # Method 1: Check info summary (usually most reliable for final cost)
        if isinstance(data, dict) and 'info' in data:
            info = data['info']
            if isinstance(info, dict) and 'model_stats' in info:
                stats = info['model_stats']
                if isinstance(stats, dict) and 'instance_cost' in stats:
                    return float(stats['instance_cost'])
        
        # Method 2: Sum from history if info is missing or zero
        total_cost = 0.0
        history = []
        if isinstance(data, list):
            history = data
        elif isinstance(data, dict) and 'history' in data:
            history = data['history']
        
        for turn in history:
            extra = turn.get('extra', {})
            if isinstance(extra, dict):
                cost = extra.get('cost', 0.0)
                if cost is not None:
                    total_cost += float(cost)
        return total_cost
    except Exception as e:
        return 0.0

all_traj_files = glob.glob("runs/**/*.traj.json", recursive=True)

run_costs = {}
total_experiment_cost = 0.0

for traj in all_traj_files:
    parts = Path(traj).parts
    if len(parts) >= 2:
        run_name = parts[1]
        cost = get_traj_cost(traj)
        run_costs[run_name] = run_costs.get(run_name, 0.0) + cost
        total_experiment_cost += cost

print(f"Total OpenAI API Cost for Solver Experiments: ${total_experiment_cost:.4f}\n")
print("Breakdown by Run:")
for run, cost in sorted(run_costs.items(), key=lambda x: x[1], reverse=True):
    print(f"  {run}: ${cost:.4f}")

