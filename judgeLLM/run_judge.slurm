#!/bin/bash
#SBATCH --job-name=judgellm_equiv
#SBATCH --output=logs/judgellm_%j.out
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00

module purge
module load cuda/12.1
module load anaconda3
source ~/.bashrc

conda activate your_env_name
export HF_HOME=/gpfs/projects/$USER/hf_cache
mkdir -p $HF_HOME

cd $SLURM_SUBMIT_DIR
python judgeLLM/equivalence_runner.py \
    --input judgeLLM/hard_negatives.json \
    --output judgeLLM/equivalence_results.json \
    --max-new-tokens 256
```