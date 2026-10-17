import random
from comfy_extras.nodes_custom_sampler import Noise_RandomNoise

class SeedNode:
    DESCRIPTION = "Produce a deterministic integer seed and a ComfyUI NOISE object, with a button to randomize the seed."
    OUTPUT_TOOLTIPS = ("The integer seed used for reproducible generations.", "ComfyUI NOISE object initialized with this seed.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 9007199254740991, "tooltip": "Random seed used to initialize noise. The same seed reproduces the same noise for the same generation settings. Limited to JavaScript-safe integers (2^53 - 1)."}),
            }
        }

    RETURN_TYPES = ("INT", "NOISE")
    RETURN_NAMES = ("seed", "noise")
    FUNCTION = "process"
    CATEGORY = "SBL"

    def process(self, seed):
        return (seed, Noise_RandomNoise(seed))