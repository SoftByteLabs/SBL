import random
from comfy_extras.nodes_custom_sampler import Noise_RandomNoise

class SeedNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("INT", "NOISE")
    RETURN_NAMES = ("seed", "noise")
    FUNCTION = "process"
    CATEGORY = "SBL"

    def process(self, seed):
        return (seed, Noise_RandomNoise(seed))