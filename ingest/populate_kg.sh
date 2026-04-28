#!/bin/bash
#SBATCH --job-name=gbd_kg_pop
#SBATCH --partition=priority
#SBATCH --time=4:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --account=prio_ji225
#SBATCH --output=./logs/kg_populate_%j.out
#SBATCH --error=./logs/kg_populate_%j.err

set -euo pipefail
echo "[$(date)] Populating GBD Knowledge Graph on $(hostname)"

cd .
export PYTHONPATH=src

set -a
source .env 2>/dev/null || true
source .env.local 2>/dev/null || true
set +a

python3 scripts/populate_knowledge_graph.py --phase all

echo "[$(date)] Done"
