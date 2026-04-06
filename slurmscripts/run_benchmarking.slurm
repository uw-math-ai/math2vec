#!/bin/bash
#SBATCH --job-name=NL_Lean_Benchmark_all_MiniLM_L6_v2
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --time=10:00
#SBATCH -o %x_%j.out

time python benchmarking/src/main.py # backslashes are for extending the line
# CLI flags here