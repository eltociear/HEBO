# Copyright (C) 2020. Huawei Technologies Co., Ltd. All rights reserved.

# This program is free software; you can redistribute it and/or modify it under
# the terms of the MIT license.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the MIT License for more details.

import os
from typing import List

import numpy as np
import pandas as pd
import torch

from mcbo import RESULTS_DIR, task_factory
from mcbo.optimizers import OptimizerBase, RandomSearch, SimulatedAnnealing, MultiArmedBandit, GeneticAlgorithm, \
    LocalSearch, BoBuilder
from mcbo.search_space import SearchSpace
from mcbo.tasks import TaskBase
from mcbo.utils.general_utils import create_save_dir, current_time_formatter, set_random_seed, load_w_pickle
from mcbo.utils.general_utils import save_w_pickle
from mcbo.utils.results_logger import ResultsLogger
from mcbo.utils.stopwatch import Stopwatch


def run_experiment(
        task: TaskBase,
        optimizers: List[OptimizerBase],
        random_seeds: List[int],
        max_num_iter: int,
        save_results_every: int = 100,
        very_verbose=False,
):
    # Basic assertion checks
    assert isinstance(task, TaskBase)
    assert isinstance(optimizers, list)
    assert isinstance(random_seeds, list)
    assert isinstance(max_num_iter, int) and max_num_iter > 0
    assert isinstance(save_results_every, int) and save_results_every > 0
    for seed in random_seeds:
        assert isinstance(seed, int)
    for optimizer in optimizers:
        assert isinstance(optimizer, OptimizerBase)

    batch_suggest = 1

    # Create the save directory
    exp_save_dir = os.path.join(RESULTS_DIR, task.name)
    create_save_dir(exp_save_dir)

    stopwatch = Stopwatch()
    results_logger = ResultsLogger()

    print(f'{current_time_formatter()} - Starting experiment for {task.name} Task')

    # Obtain maximum optimizer name length for formatting
    max_name_len = 0
    for optimizer in optimizers:
        max_name_len = max(max_name_len, len(optimizer.name))

    for optimizer in optimizers:

        optim_save_dir = os.path.join(exp_save_dir, optimizer.name)
        create_save_dir(optim_save_dir)

        for i, seed in enumerate(random_seeds):
            set_random_seed(seed)
            task.restart()
            optimizer.restart()
            stopwatch.reset()
            results_logger.restart()
            start_iter = 1

            print(
                f'{current_time_formatter()} - Optimizer : {optimizer.name:>{max_name_len}} - Seed {seed} {i + 1:2d}/{len(random_seeds):2d}')

            save_y_path = os.path.join(optim_save_dir, f'seed_{seed}_results.csv')
            save_x_path = os.path.join(optim_save_dir, f'seed_{seed}_x.pkl')
            save_time_path = os.path.join(optim_save_dir, f'seed_{seed}_time.pkl')
            if os.path.exists(save_y_path) and os.path.exists(save_x_path):
                x = load_w_pickle(save_x_path)
                x = pd.DataFrame.from_dict(x)

                results = pd.read_csv((save_y_path))
                y = results["f(x)"].values.reshape((-1, 1))
                elapsed_time = results["Elapsed Time"].values.flatten()

                for iter_num in range(len(x)):
                    x_next = x[iter_num:iter_num + batch_suggest]
                    y_next = y[iter_num:iter_num + batch_suggest]
                    task.increment_n_evals(len(x_next))
                    if hasattr(optimizer, "x_init") and optimizer.x_init is not None:
                        optimizer.x_init = optimizer.x_init[len(x_next):]
                    optimizer.observe(x=x_next, y=y_next)

                    results_logger.append(
                        eval_num=len(optimizer.data_buffer),
                        x=x_next.iloc[0].to_dict(),
                        y=y_next[0, 0],
                        y_star=optimizer.best_y,
                        elapsed_time=elapsed_time[iter_num]
                    )

                if os.path.exists(save_time_path):
                    time_dict = load_w_pickle(save_time_path)
                    optimizer.set_time_from_dict(time_dict)

                start_iter = len(x) // batch_suggest + 1
                print(
                    f'{current_time_formatter()} - Loaded {len(x)} existing points... y* {optimizer.best_y:.3f}')

            # Main loop
            for iter_num in range(start_iter, max_num_iter + 1):

                torch.cuda.empty_cache()  # Clear cached memory

                # Suggest a point
                stopwatch.start()
                x_next = optimizer.suggest(batch_suggest)
                stopwatch.stop()

                # Compute the Black-box value
                y_next = task(x_next)

                # Observe the point
                stopwatch.start()
                optimizer.observe(x_next, y_next)
                stopwatch.stop()

                filtr_ind = np.arange(len(y_next))[np.isnan(y_next).sum(-1) == 0]
                y_next = y_next[filtr_ind]
                x_next = x_next.iloc[filtr_ind]
                if len(x_next) == 0:
                    continue

                results_logger.append(
                    eval_num=len(optimizer.data_buffer),
                    x=x_next.iloc[0].to_dict(),
                    y=y_next[0, 0],
                    y_star=optimizer.best_y,
                    elapsed_time=stopwatch.get_total_time()
                )

                if very_verbose:
                    print(
                        f'{current_time_formatter()} - Iteration {iter_num:3d}/{max_num_iter:3d} - y {y_next[0, 0]:.3f} - y* {optimizer.best_y:.3f}')

                if iter_num % save_results_every == 0:
                    results_logger.save(save_y_path=save_y_path, save_x_path=save_x_path)
                    # save running times
                    if hasattr(optimizer, "get_time_dicts"):
                        save_w_pickle(optimizer.get_time_dicts(), save_time_path)

            results_logger.save(save_y_path=save_y_path, save_x_path=save_x_path)
            # save running times
            if hasattr(optimizer, "get_time_dicts"):
                save_w_pickle(optimizer.get_time_dicts(), save_time_path)

    print(f'{current_time_formatter()} - Experiment finished.')


def get_task_and_search_space(task_id: str, dtype: torch.dtype = torch.float64, **task_kwargs):
    task_name = None
    if task_id == "rna_inverse_fold":
        task_kwargs = {'target': 65}
    elif task_id == "ackley-53":
        task_name = "ackley"
        num_dims = [50, 3]
        variable_type = ['nominal', 'num']
        num_categories = [2, None]
        task_name_suffix = " 50-nom-2 3-num"
        lb = np.zeros(53)
        lb[-3:] = -1
        task_kwargs = dict(num_dims=num_dims, variable_type=variable_type, num_categories=num_categories,
                           task_name_suffix=task_name_suffix, lb=lb, ub=1)
    elif task_id == 'xgboost_opt':
        dataset_id = "mnist"
        task_kwargs = dict(dataset_id=dataset_id)
    elif task_id == 'aig_optimization_hyp':
        task_kwargs = {'designs_group_id': "sin", "operator_space_id": "basic", "objective": "both",
                       "seq_operators_pattern_id": "basic_w_post_map"}
    elif task_id == 'svm_opt':
        task_kwargs = dict()
    elif "ackley" in task_id or "levy" in task_id:
        task_kwargs = None
        n_cats = 11
        for synth in ["ackley", "levy"]:
            if synth not in task_id:
                continue
            if task_id == synth:
                dim = 20
                task_name_suffix = None
            else:
                dim = int(task_id.split("-")[-1])
                assert task_id == f"{synth}-{dim}"
                task_name_suffix = f"{dim}-nom-{n_cats}"
            task_kwargs = {'num_dims': dim, 'variable_type': 'nominal', 'num_categories': n_cats,
                           "task_name_suffix": task_name_suffix}
            task_name = synth
        assert task_kwargs is not None
    elif task_id == 'mig_optimization':
        task_kwargs = {'ntk_name': "sqrt", "objective": "both"}
    elif task_id == 'aig_optimization':
        task_kwargs = {'designs_group_id': "sin", "operator_space_id": "basic", "objective": "both"}
    elif task_id == 'antibody_design':
        task_kwargs = {'num_cpus': 5, 'first_cpu': 0, 'absolut_dir': task_kwargs.get("absolut_dir")}
    elif task_id == 'pest':
        task_kwargs = {}
    else:
        raise ValueError(task_id)

    if task_name is None:
        task_name = task_id
    task = task_factory(task_name=task_name, **task_kwargs)
    return task, task.get_search_space(dtype=dtype)


def get_opt(search_space: SearchSpace, task: TaskBase, full_opt_name: str, bo_n_init: int = 20,
            dtype: torch.dtype = torch.float64,
            bo_device=torch.device("cpu")):
    opt_kwargs = dict(search_space=search_space, dtype=dtype,
                      input_constraints=task.input_constraints)
    if full_opt_name == "rs":
        opt = RandomSearch(**opt_kwargs)
    elif full_opt_name == "sa":
        opt = SimulatedAnnealing(**opt_kwargs)
    elif full_opt_name == "mab":
        opt = MultiArmedBandit(**opt_kwargs)
    elif full_opt_name == "ga":
        opt = GeneticAlgorithm(**opt_kwargs)
    elif full_opt_name == "ls":
        opt = LocalSearch(**opt_kwargs)
    else:
        bo_opt_kwargs = dict(n_init=bo_n_init, device=bo_device, **opt_kwargs)
        bo_name_split = full_opt_name.split("__")
        model_id = bo_name_split[0]
        acq_opt_id = bo_name_split[1]
        acq_func_id = bo_name_split[2]
        tr_id = None
        if len(bo_name_split) > 3:
            assert bo_name_split[3] == "tr"
            tr_id = "basic"
        opt_builder = BoBuilder(model_id=model_id, acq_opt_id=acq_opt_id, acq_func_id=acq_func_id,
                                tr_id=tr_id)
        opt = opt_builder.build_bo(
            **bo_opt_kwargs
        )

    return opt
