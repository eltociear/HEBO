import argparse
import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(os.path.realpath(__file__)).parent.parent))

from mcbo.utils.experiment_utils import run_experiment, get_task_and_search_space, get_opt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=True, description='CombBopt - Combinatorial Tasks')
    parser.add_argument("--device_id", type=int, default=0, help="Cuda device id (cpu is used if id is negative)")
    parser.add_argument("--task_id", type=str, required=True, help="Name of the task")
    parser.add_argument("--optimizers_ids", type=str, nargs="+", required=True, help="Name of the methods to run")
    parser.add_argument("--seeds", type=int, nargs="+", required=True, help="Seeds to run")
    parser.add_argument("--verbose", type=int, default=1, help="Verbosity level")

    # Antigen binding task
    parser.add_argument("--absolut_dir", type=str, default=None, required=False, help="Path to Absolut! executer.")

    args = parser.parse_args()

    dtype_ = torch.float64
    task_id_ = args.task_id
    task, search_space = get_task_and_search_space(task_id=task_id_, dtype=dtype_, absolut_dir=args.absolut_dir)

    bo_n_init_ = 20
    if args.device_id >= 0 and torch.cuda.is_available():
        bo_device_ = torch.device(f'cuda:{args.device_id}')
    else:
        bo_device_ = torch.device("cpu")

    max_num_iter = 200
    random_seeds = args.seeds

    selected_optimizers = []
    for opt_id in args.optimizers_ids:
        opt = get_opt(
            search_space=search_space,
            task=task,
            full_opt_name=opt_id,
            bo_n_init=bo_n_init_,
            dtype=dtype_,
            bo_device=bo_device_
        )

        run_experiment(
            task=task,
            optimizers=[opt],
            random_seeds=random_seeds,
            max_num_iter=max_num_iter,
            save_results_every=max_num_iter,
            very_verbose=args.verbose > 1
        )
