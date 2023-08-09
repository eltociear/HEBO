# Copyright (C) 2023. Huawei Technologies Co., Ltd. All rights reserved.

# This program is free software; you can redistribute it and/or modify it under
# the terms of the MIT license.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the MIT License for more details.




import dmc2gym
from envs.point_mass.local_expert_policy import SACExpert
import os
from types import MethodType
from dm_control.utils import rewards


# modify initialization
def new_get_reward(self, physics):
    """Returns a reward to the agent."""
    target_size = physics.named.model.geom_size['target', 0]
    near_target = rewards.tolerance(physics.mass_to_target_dist(),
                                    bounds=(0, target_size))
    control_reward = rewards.tolerance(physics.control(), margin=1,
                                       value_at_margin=0,
                                       sigmoid='quadratic').mean()
    small_control = (control_reward + 4) / 5
    return near_target * small_control


def create_point_mass_and_control(orig_cwd='./',
                                  device="cpu",
                                  sparse=False):
    # create env
    env = dmc2gym.make('point_mass', 'easy')

    # modify target (to create simple task)
    if sparse:
        env.env._env._task.get_reward = MethodType(new_get_reward, env.env._env._task)

    # env.env._env.physics.named.model.geom_size['target', 0] = 0.1
    # env.env._env._task._target_size = 0.1

    path = os.path.join(orig_cwd, 'envs', 'point_mass', 'models')

    control_dict = {
        "MediumSAC": {
            "coord": None,
            "local_expert": SACExpert(env, path, device)
        },
    }

    return env, control_dict