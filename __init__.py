import os
import folder_paths

from .GlobalPromptNode import GlobalPromptNode
from .ResolutionNode import ResolutionNode
from .MathEvaluatorNode import MathEvaluatorNode
from .SeedNode import SeedNode
from .MathScratchpadNode import MathScratchpadNode
from .YuE2Instrumental import YuE2Instrumental

NODE_CLASS_MAPPINGS = {
    "SBL_GlobalPrompt": GlobalPromptNode,
    "SBL_Resolution": ResolutionNode,
    "SBL_MathEvaluator": MathEvaluatorNode,
    "SBL_Seed": SeedNode,
    "SBL_MathScratchpadNode": MathScratchpadNode,
    "SBL_YuE2Instrumental": YuE2Instrumental,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SBL_GlobalPrompt": "Global Prompt (Pos/Neg)",
    "SBL_Resolution": "Resolution",
    "SBL_MathEvaluator": "Math Evaluator",
    "SBL_Seed": "Seed",
    "SBL_MathScratchpadNode": "Math Scratchpad",
    "SBL_YuE2Instrumental": "YuE2 Instrumental Prep",
}

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]