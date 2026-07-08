import os
import random
from typing import Any

import numpy as np


class SeedManager:
    _instances: dict[str, int] = {}

    @staticmethod
    def set_seed(seed: int, set_torch: bool = False, set_tf: bool = False,
                 set_python: bool = True, set_numpy: bool = True) -> int:
        if set_python:
            random.seed(seed)
        if set_numpy:
            np.random.seed(seed)
        if set_torch:
            try:
                import torch
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
            except ImportError:
                pass
        if set_tf:
            try:
                import tensorflow as tf
                tf.random.set_seed(seed)
            except ImportError:
                pass
        os.environ["PYTHONHASHSEED"] = str(seed)
        SeedManager._instances["global"] = seed
        return seed

    @staticmethod
    def get_seed(name: str = "global") -> int | None:
        return SeedManager._instances.get(name)

    @staticmethod
    def register_seed(name: str, seed: int):
        SeedManager._instances[name] = seed

    @staticmethod
    def generate_seed(base: int = 42, offset: int = 0) -> int:
        return base + offset

    @staticmethod
    def reset():
        SeedManager._instances.clear()
