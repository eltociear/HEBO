# Copyright (C) 2023. Huawei Technologies Co., Ltd. All rights reserved.

# This program is free software; you can redistribute it and/or modify it under
# the terms of the MIT license.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the MIT License for more details.




import numpy as np
import torch
import os

class SACExpert:

    def __init__(self, env, path, device="cpu"):

        from agents.common.model import TanhGaussianPolicy, SamplerPolicy
        # hyper-params
        policy_arch = '32-32'
        policy_log_std_multiplier = 1.0
        policy_log_std_offset = -1.0

        # load expert policy
        expert_policy = TanhGaussianPolicy(
            env.observation_space.shape[0],
            env.action_space.shape[0],
            policy_arch,
            log_std_multiplier=policy_log_std_multiplier,
            log_std_offset=policy_log_std_offset,
        )
        glob_path = os.path.join(path, 'medium_sac')
        expert_policy.load_state_dict(torch.load(glob_path))
        expert_policy.to(device)
        self.sampling_expert_policy = SamplerPolicy(expert_policy, device=device)

    def get_action(self, observation, init_action=None, env=None):
        with torch.no_grad():
            expert_action = self.sampling_expert_policy(
                np.expand_dims(observation, 0), deterministic=True
            )[0, :]
        # to further decrease performance
        expert_action[0] *= 0.2
        return np.clip(expert_action, a_min=-0.99, a_max=0.99)  # expert_action
