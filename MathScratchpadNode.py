import sys
import io
from aiohttp import web
from server import PromptServer


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


# ── Custom API route ──────────────────────────────────────────────────────────
@PromptServer.instance.routes.post("/sbl/scratchpad/evaluate")
async def scratchpad_evaluate(request):
    try:
        data = await request.json()
        src  = data.get("expressions", "")
    except Exception as e:
        return web.json_response({"error": f"Bad request: {e}"}, status=400)

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer

    try:
        exec(src, {})
    except Exception as ex:
        print(f"ERROR: {ex}")
    finally:
        sys.stdout = old_stdout

    return web.json_response({"output": buffer.getvalue()})