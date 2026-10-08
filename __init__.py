import os
import folder_paths

from .GlobalPromptNode import GlobalPromptNode
from .ResolutionNode import ResolutionNode
from .MathEvaluatorNode import MathEvaluatorNode
from .SeedNode import SeedNode
from .Qwen2512ResT2I import Qwen2512ResT2I
from .ZiTResT2I import ZiTResT2I
from .MathScratchpadNode import MathScratchpadNode
from .YuE2Instrumental import YuE2Instrumental

NODE_CLASS_MAPPINGS = {
    "SBL_GlobalPrompt": GlobalPromptNode,
    "SBL_Resolution": ResolutionNode,
    "SBL_MathEvaluator": MathEvaluatorNode,
    "SBL_Seed": SeedNode,
    "SBL_Qwen2512ResT2I": Qwen2512ResT2I,
    "SBL_ZiTResT2I": ZiTResT2I,
    "SBL_MathScratchpadNode": MathScratchpadNode,
    "SBL_YuE2Instrumental": YuE2Instrumental,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SBL_GlobalPrompt": "Global Prompt (Pos/Neg)",
    "SBL_Resolution": "Resolution",
    "SBL_MathEvaluator": "Math Evaluator",
    "SBL_Seed": "Seed",
    "SBL_Qwen2512ResT2I": "Qwen 2512 t2i resolutions",
    "SBL_ZiTResT2I": "ZiT t2i resolutions",
    "SBL_MathScratchpadNode": "Math Scratchpad",
    "SBL_YuE2Instrumental": "YuE2 Instrumental Prep",
}

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]