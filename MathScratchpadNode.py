from aiohttp import web
from server import PromptServer

from .MathEvaluatorNode import SafeMathInterpreter


class MathScratchpadNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expressions": ("STRING", {
                    "multiline": True,
                    "default": "import math\nt = 12\nrawframes = t * 24 + 1\nltxframes = 8 * math.floor((rawframes - 1) / 8)\nprint(ltxframes + 1)\nprint(ltxframes / 24)\nprint(ltxframes / 8)"
                }),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "SBL"
    OUTPUT_NODE = True

    def noop(self, expressions):
        return {}


@PromptServer.instance.routes.post("/sbl/scratchpad/evaluate")
async def scratchpad_evaluate(request):
    try:
        data = await request.json()
        source = data.get("expressions", "")
    except Exception as ex:
        return web.json_response({"error": f"Bad request: {ex}"}, status=400)

    try:
        interpreter = SafeMathInterpreter(capture_output=True)
        interpreter.run(source)
        output = interpreter.get_output()
        return web.json_response({"output": output})
    except Exception as ex:
        return web.json_response({"error": str(ex)}, status=400)
