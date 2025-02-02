# Copyright (C) 2020. Huawei Technologies Co., Ltd. All rights reserved.

# This program is free software; you can redistribute it and/or modify it under
# the terms of the MIT license.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the MIT License for more details.

import numpy as np
import torch

from mcbo.search_space.params.param import Parameter


class PowPara(Parameter):
    def __init__(self, param_dict: dict, dtype: torch.dtype):
        super().__init__(param_dict, dtype)
        assert 0 < param_dict.get('lb') < param_dict.get('ub'), 'The lower and upper bound must be greater than 0'
        self.base = param_dict.get('base', 10.)
        self.lb = np.log(param_dict.get('lb')) / np.log(self.base)
        self.ub = np.log(param_dict.get('ub')) / np.log(self.base)

    def sample(self, num=1):
        assert (num > 0)
        return self.base ** np.random.uniform(self.lb, self.ub, num)

    def transform(self, x) -> torch.Tensor:
        log_x = np.log(x) / np.log(self.base)

        # Normalise
        normalised_log_x = (log_x - self.lb) / (self.ub - self.lb)

        return torch.tensor(normalised_log_x, dtype=self.dtype)

    def inverse_transform(self, x: torch.Tensor) -> np.ndarray:
        x = x.cpu().numpy()
        # Un-normalise
        log_x = (self.ub - self.lb) * x + self.lb

        return self.base ** log_x

    @property
    def is_disc(self) -> bool:
        return False

    @property
    def is_cont(self) -> bool:
        return True

    @property
    def is_nominal(self) -> bool:
        return False

    @property
    def is_ordinal(self) -> bool:
        return False

    @property
    def is_permutation(self) -> bool:
        return False

    @property
    def is_disc_after_transform(self) -> bool:
        return False

    @property
    def opt_lb(self):
        return float(self.lb)

    @property
    def opt_ub(self):
        return float(self.ub)
