class MathEvaluatorNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expressions": ("STRING", {
                    "multiline": True,
                    "default": "a = w/x\nb = y+z"
                }),
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "INT", "INT")
    RETURN_NAMES = ("a", "b", "a", "b")
    FUNCTION = "evaluate"
    CATEGORY = "SBL"

    def evaluate(self, expressions, w=None, x=None, y=None, z=None):
        # Initialize variables - convert None to 0 for unconnected inputs
        variables = {
            'w': w if w is not None else 0.0,
            'x': x if x is not None else 0.0,
            'y': y if y is not None else 0,
            'z': z if z is not None else 0,
            'a': 0.0,
            'b': 0
        }

        # Add math functions for convenience
        import math
        safe_dict = {
            '__builtins__': {},
            # Math functions
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'pow': pow,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'pi': math.pi,
            'e': math.e,
            'log': math.log,
            'log10': math.log10,
            'floor': math.floor,
            'ceil': math.ceil,
        }

        # Add our variables to the safe dictionary
        safe_dict.update(variables)

        try:
            # Split expressions by lines and evaluate each
            lines = expressions.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    exec('\n'.join(lines), safe_dict)

            # Extract results
            a_result_float = float(safe_dict.get('a', 0.0))
            b_result_float = float(safe_dict.get('b', 0.0))
            a_result_int = int(safe_dict.get('a', 0))
            b_result_int = int(safe_dict.get('b', 0))

        except Exception as e:
            print(f"MathEvaluator Error: {str(e)}")
            a_result_float = 0.0
            b_result_float = 0.0
            a_result_int = 0
            b_result_int = 0

        return (a_result_float, b_result_float, a_result_int, b_result_int)
