import ast
import cmath
import math
import re
import statistics
from decimal import Decimal
from fractions import Fraction


class SafeMathError(Exception):
    """Raised when the restricted math language rejects an operation."""


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _SafeCallable:
    __slots__ = ("name", "func")

    def __init__(self, name, func):
        self.name = name
        self.func = func


class _SafeModule:
    __slots__ = ("name", "members")

    def __init__(self, name, members):
        self.name = name
        self.members = members


class SafeMathInterpreter:
    """
    Small AST interpreter for calculator-style Python.

    It deliberately does NOT execute compiled Python.  Instead it parses the
    source with ast.parse() and handles only an allow-list of syntax, functions,
    modules and operators.  This keeps the useful calculator parts of Python
    without exposing files, processes, imports, object introspection, etc.
    """

    MAX_SOURCE_CHARS = 50_000
    MAX_AST_NODES = 4_000
    MAX_COLLECTION_ITEMS = 100_000
    MAX_TOTAL_ITERATIONS = 100_000
    MAX_WHILE_ITERATIONS = 10_000
    MAX_POWER_EXPONENT = 10_000
    MAX_SHIFT = 10_000
    MAX_OUTPUT_CHARS = 100_000
    MAX_INT_BITS = 131_072
    MAX_DECIMAL_DIGITS = 100_000

    def __init__(self, initial_variables=None, capture_output=False):
        self.output = []
        self.capture_output = capture_output
        self.total_iterations = 0

        self.modules = self._build_modules()
        self.env = self._build_base_environment()
        if initial_variables:
            for name, value in initial_variables.items():
                self._validate_name(name)
                self.env[name] = self._check_value(value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, source):
        if not isinstance(source, str):
            raise SafeMathError("Expressions must be text.")
        if len(source) > self.MAX_SOURCE_CHARS:
            raise SafeMathError("Expression text is too large.")

        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as ex:
            line = ex.lineno or "?"
            raise SafeMathError(f"Syntax error on line {line}: {ex.msg}") from None

        node_count = sum(1 for _ in ast.walk(tree))
        if node_count > self.MAX_AST_NODES:
            raise SafeMathError("Expression is too complex.")

        self._exec_block(tree.body)
        return self.env

    def get_output(self):
        return "".join(self.output)

    # ------------------------------------------------------------------
    # Safe environment
    # ------------------------------------------------------------------
    def _wrap(self, name, func):
        return _SafeCallable(name, func)

    def _build_modules(self):
        math_names = [
            "acos", "acosh", "asin", "asinh", "atan", "atan2", "atanh",
            "cbrt", "ceil", "copysign", "cos", "cosh", "degrees", "dist",
            "erf", "erfc", "exp", "exp2", "expm1", "fabs", "floor", "fmod",
            "frexp", "fsum", "gamma", "gcd", "hypot", "isclose", "isfinite",
            "isinf", "isnan", "isqrt", "lcm", "ldexp", "lgamma", "log",
            "log10", "log1p", "log2", "modf", "nextafter", "pow", "prod",
            "radians", "remainder", "sin", "sinh", "sqrt", "tan", "tanh",
            "trunc", "ulp"
        ]
        math_members = {
            name: self._wrap(f"math.{name}", getattr(math, name))
            for name in math_names
            if hasattr(math, name)
        }
        math_members.update({
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "inf": math.inf,
            "nan": math.nan,
            "factorial": self._wrap("math.factorial", self._safe_factorial),
            "comb": self._wrap("math.comb", self._safe_comb),
            "perm": self._wrap("math.perm", self._safe_perm),
        })

        statistics_names = [
            "mean", "fmean", "geometric_mean", "harmonic_mean", "median",
            "median_low", "median_high", "median_grouped", "mode", "multimode",
            "pstdev", "pvariance", "stdev", "variance", "quantiles",
            "correlation", "covariance", "linear_regression"
        ]
        statistics_members = {
            name: self._wrap(f"statistics.{name}", getattr(statistics, name))
            for name in statistics_names
            if hasattr(statistics, name)
        }

        cmath_names = [
            "acos", "acosh", "asin", "asinh", "atan", "atanh", "cos", "cosh",
            "exp", "isclose", "isfinite", "isinf", "isnan", "log", "log10",
            "phase", "polar", "rect", "sin", "sinh", "sqrt", "tan", "tanh"
        ]
        cmath_members = {
            name: self._wrap(f"cmath.{name}", getattr(cmath, name))
            for name in cmath_names
            if hasattr(cmath, name)
        }
        cmath_members.update({
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "inf": math.inf,
            "infj": complex(0.0, math.inf),
            "nan": math.nan,
            "nanj": complex(0.0, math.nan),
        })

        return {
            "math": _SafeModule("math", math_members),
            "statistics": _SafeModule("statistics", statistics_members),
            "cmath": _SafeModule("cmath", cmath_members),
        }

    def _build_base_environment(self):
        env = {
            "abs": self._wrap("abs", abs),
            "all": self._wrap("all", all),
            "any": self._wrap("any", any),
            "bool": self._wrap("bool", bool),
            "complex": self._wrap("complex", complex),
            "Decimal": self._wrap("Decimal", Decimal),
            "Fraction": self._wrap("Fraction", Fraction),
            "divmod": self._wrap("divmod", divmod),
            "enumerate": self._wrap("enumerate", enumerate),
            "float": self._wrap("float", float),
            "int": self._wrap("int", int),
            "len": self._wrap("len", len),
            "list": self._wrap("list", list),
            "max": self._wrap("max", max),
            "min": self._wrap("min", min),
            "pow": self._wrap("pow", self._safe_pow),
            "range": self._wrap("range", self._safe_range),
            "reversed": self._wrap("reversed", reversed),
            "round": self._wrap("round", round),
            "set": self._wrap("set", set),
            "sorted": self._wrap("sorted", sorted),
            "str": self._wrap("str", str),
            "sum": self._wrap("sum", sum),
            "tuple": self._wrap("tuple", tuple),
            "zip": self._wrap("zip", zip),
            "print": self._wrap("print", self._safe_print),
            "True": True,
            "False": False,
            "None": None,
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
            "inf": math.inf,
            "nan": math.nan,
        }

        # Backward compatibility with the original Math Evaluator: common
        # math names such as sqrt(), floor(), sin(), log(), etc. are available
        # directly without requiring "import math".
        for name, value in self.modules["math"].members.items():
            env.setdefault(name, value)

        return env

    # ------------------------------------------------------------------
    # Resource-limited helpers
    # ------------------------------------------------------------------
    def _safe_print(self, *args, sep=" ", end="\n"):
        if not isinstance(sep, str) or not isinstance(end, str):
            raise SafeMathError("print sep/end must be strings.")
        text = sep.join(str(value) for value in args) + end
        current = sum(len(part) for part in self.output)
        if current + len(text) > self.MAX_OUTPUT_CHARS:
            raise SafeMathError("Printed output is too large.")
        if self.capture_output:
            self.output.append(text)
        else:
            print(text, end="")

    def _safe_range(self, *args):
        result = range(*args)
        if len(result) > self.MAX_COLLECTION_ITEMS:
            raise SafeMathError("range() is too large.")
        return result

    def _safe_pow(self, base, exponent, modulus=None):
        self._guard_numeric_operation(base, exponent, power=True)
        if modulus is None:
            return self._check_value(pow(base, exponent))
        return self._check_value(pow(base, exponent, modulus))

    def _safe_factorial(self, value):
        value = int(value)
        if value < 0 or value > 10_000:
            raise SafeMathError("factorial() input must be between 0 and 10000.")
        return math.factorial(value)

    def _safe_comb(self, n, k):
        n = int(n)
        k = int(k)
        if n < 0 or k < 0 or n > 100_000:
            raise SafeMathError("comb() arguments are outside the allowed range.")
        return math.comb(n, k)

    def _safe_perm(self, n, k=None):
        n = int(n)
        if k is not None:
            k = int(k)
        if n < 0 or n > 100_000 or (k is not None and k < 0):
            raise SafeMathError("perm() arguments are outside the allowed range.")
        effective_k = n if k is None else min(k, n)
        if n > 1 and effective_k * math.log2(n) > self.MAX_INT_BITS:
            raise SafeMathError("perm() result would be too large.")
        return math.perm(n, k)

    def _guard_power(self, exponent):
        # Fraction and Decimal are numeric exponents too. Avoid only checking
        # built-in int/float; that previously allowed enormous Fraction powers.
        if isinstance(exponent, complex):
            if not math.isfinite(exponent.real) or not math.isfinite(exponent.imag):
                raise SafeMathError("Exponent must be finite.")
            size = abs(exponent)
        elif isinstance(exponent, (int, float, Fraction, Decimal)):
            try:
                size = abs(exponent)
            except (OverflowError, ValueError):
                raise SafeMathError("Exponent is outside the allowed range.") from None
        else:
            raise SafeMathError("Exponent must be a number.")
        if size > self.MAX_POWER_EXPONENT or (isinstance(size, float) and not math.isfinite(size)):
            raise SafeMathError("Exponent is too large.")

    def _guard_numeric_operation(self, left, right, power=False):
        # Reject huge integer/fraction arithmetic before constructing it.
        def bits(value):
            if isinstance(value, int):
                return value.bit_length()
            if isinstance(value, Fraction):
                return max(value.numerator.bit_length(), value.denominator.bit_length())
            if isinstance(value, Decimal):
                return len(value.as_tuple().digits) * 4
            return 0
        left_bits, right_bits = bits(left), bits(right)
        if power:
            self._guard_power(right)
            if isinstance(right, (int, Fraction, Decimal)):
                if left_bits * int(abs(right)) > self.MAX_INT_BITS * 2:
                    raise SafeMathError("Power result would be too large.")
        elif left_bits + right_bits > self.MAX_INT_BITS * 2:
            raise SafeMathError("Arithmetic result would be too large.")

    def _consume_iterations(self, amount=1):
        self.total_iterations += amount
        if self.total_iterations > self.MAX_TOTAL_ITERATIONS:
            raise SafeMathError("Iteration limit exceeded.")

    def _check_value(self, value):
        if isinstance(value, int) and value.bit_length() > self.MAX_INT_BITS:
            raise SafeMathError("Integer value is too large.")
        if isinstance(value, Fraction) and max(value.numerator.bit_length(), value.denominator.bit_length()) > self.MAX_INT_BITS:
            raise SafeMathError("Fraction value is too large.")
        if isinstance(value, Decimal):
            if len(value.as_tuple().digits) > self.MAX_DECIMAL_DIGITS:
                raise SafeMathError("Decimal value has too many digits.")
        if isinstance(value, str) and len(value) > self.MAX_OUTPUT_CHARS:
            raise SafeMathError("String value is too large.")
        if isinstance(value, (list, tuple, set, dict, range)) and len(value) > self.MAX_COLLECTION_ITEMS:
            raise SafeMathError("Collection is too large.")
        return value

    def _validate_name(self, name):
        if not isinstance(name, str) or not name.isidentifier():
            raise SafeMathError(f"Invalid variable name: {name!r}")
        if name.startswith("_"):
            raise SafeMathError("Names beginning with '_' are not allowed.")

    # ------------------------------------------------------------------
    # Statement interpreter
    # ------------------------------------------------------------------
    def _exec_block(self, statements):
        for statement in statements:
            self._exec_statement(statement)

    def _exec_statement(self, node):
        if isinstance(node, ast.Expr):
            result = self._eval_expr(node.value)
            # The Scratchpad shows standalone expressions without requiring
            # print(...). A print() call already produced its own output.
            if self.capture_output and result is not None and not (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "print"
            ):
                self._safe_print(self._check_value(result))
            return

        if isinstance(node, ast.Assign):
            value = self._eval_expr(node.value)
            for target in node.targets:
                self._assign_target(target, value)
            return

        if isinstance(node, ast.AnnAssign):
            if node.value is None:
                raise SafeMathError("Annotation-only assignments are not supported.")
            self._assign_target(node.target, self._eval_expr(node.value))
            return

        if isinstance(node, ast.AugAssign):
            current = self._load_target(node.target)
            value = self._apply_binop(node.op, current, self._eval_expr(node.value))
            self._assign_target(node.target, value)
            return

        if isinstance(node, ast.If):
            branch = node.body if self._truthy(self._eval_expr(node.test)) else node.orelse
            self._exec_block(branch)
            return

        if isinstance(node, ast.For):
            iterable = self._materialize_iterable(self._eval_expr(node.iter))
            broke = False
            try:
                for item in iterable:
                    self._consume_iterations()
                    self._assign_target(node.target, item)
                    try:
                        self._exec_block(node.body)
                    except _ContinueSignal:
                        continue
            except _BreakSignal:
                broke = True
            if not broke:
                self._exec_block(node.orelse)
            return

        if isinstance(node, ast.While):
            count = 0
            broke = False
            try:
                while self._truthy(self._eval_expr(node.test)):
                    count += 1
                    self._consume_iterations()
                    if count > self.MAX_WHILE_ITERATIONS:
                        raise SafeMathError("while-loop iteration limit exceeded.")
                    try:
                        self._exec_block(node.body)
                    except _ContinueSignal:
                        continue
            except _BreakSignal:
                broke = True
            if not broke:
                self._exec_block(node.orelse)
            return

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in self.modules:
                    raise SafeMathError(f"Import of '{alias.name}' is not allowed.")
                target_name = alias.asname or alias.name
                self._validate_name(target_name)
                self.env[target_name] = self.modules[alias.name]
            return

        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if node.level != 0 or module_name not in self.modules:
                raise SafeMathError(f"Import from '{module_name}' is not allowed.")
            module = self.modules[module_name]
            for alias in node.names:
                if alias.name == "*":
                    raise SafeMathError("Wildcard imports are not allowed.")
                if alias.name not in module.members:
                    raise SafeMathError(f"'{alias.name}' is not available from {module_name}.")
                target_name = alias.asname or alias.name
                self._validate_name(target_name)
                self.env[target_name] = module.members[alias.name]
            return

        if isinstance(node, ast.Pass):
            return

        if isinstance(node, ast.Break):
            raise _BreakSignal()

        if isinstance(node, ast.Continue):
            raise _ContinueSignal()

        raise SafeMathError(f"Statement '{type(node).__name__}' is not allowed.")

    # ------------------------------------------------------------------
    # Expression interpreter
    # ------------------------------------------------------------------
    def _eval_expr(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, bytes)) and len(node.value) > self.MAX_OUTPUT_CHARS:
                raise SafeMathError("Literal is too large.")
            if isinstance(node.value, bytes):
                raise SafeMathError("Bytes literals are not supported.")
            return node.value

        if isinstance(node, ast.Name):
            self._validate_name(node.id)
            if node.id not in self.env:
                raise SafeMathError(f"Unknown name '{node.id}'.")
            return self.env[node.id]

        if isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            return self._apply_binop(node.op, left, right)

        if isinstance(node, ast.UnaryOp):
            value = self._eval_expr(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.Not):
                return not self._truthy(value)
            if isinstance(node.op, ast.Invert):
                return ~value
            raise SafeMathError(f"Unary operator '{type(node.op).__name__}' is not allowed.")

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = True
                for value_node in node.values:
                    result = self._eval_expr(value_node)
                    if not self._truthy(result):
                        return result
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for value_node in node.values:
                    result = self._eval_expr(value_node)
                    if self._truthy(result):
                        return result
                return result
            raise SafeMathError("Boolean operator is not allowed.")

        if isinstance(node, ast.Compare):
            left = self._eval_expr(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_expr(comparator)
                if not self._apply_compare(op, left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.IfExp):
            branch = node.body if self._truthy(self._eval_expr(node.test)) else node.orelse
            return self._eval_expr(branch)

        if isinstance(node, ast.Call):
            callable_obj = self._eval_expr(node.func)
            if not isinstance(callable_obj, _SafeCallable):
                raise SafeMathError("Only approved functions may be called.")
            args = [self._eval_expr(arg) for arg in node.args]
            kwargs = {}
            for keyword in node.keywords:
                if keyword.arg is None:
                    raise SafeMathError("**kwargs expansion is not allowed.")
                kwargs[keyword.arg] = self._eval_expr(keyword.value)
            try:
                result = callable_obj.func(*args, **kwargs)
            except SafeMathError:
                raise
            except Exception as ex:
                raise SafeMathError(f"{callable_obj.name}(): {ex}") from None
            return self._check_value(result)

        if isinstance(node, ast.Attribute):
            value = self._eval_expr(node.value)
            if not isinstance(value, _SafeModule):
                raise SafeMathError("Object attribute access is not allowed.")
            if node.attr.startswith("_") or node.attr not in value.members:
                raise SafeMathError(f"'{node.attr}' is not available from {value.name}.")
            return value.members[node.attr]

        if isinstance(node, ast.List):
            return self._check_value([self._eval_expr(item) for item in node.elts])

        if isinstance(node, ast.Tuple):
            return self._check_value(tuple(self._eval_expr(item) for item in node.elts))

        if isinstance(node, ast.Set):
            return self._check_value({self._eval_expr(item) for item in node.elts})

        if isinstance(node, ast.Dict):
            result = {}
            for key_node, value_node in zip(node.keys, node.values):
                if key_node is None:
                    raise SafeMathError("Dictionary unpacking is not allowed.")
                result[self._eval_expr(key_node)] = self._eval_expr(value_node)
            return self._check_value(result)

        if isinstance(node, ast.Subscript):
            container = self._eval_expr(node.value)
            if not isinstance(container, (list, tuple, dict, str, range)):
                raise SafeMathError("Subscript access is only allowed on local containers.")
            index = self._eval_slice(node.slice)
            try:
                return self._check_value(container[index])
            except Exception as ex:
                raise SafeMathError(f"Subscript error: {ex}") from None

        if isinstance(node, ast.JoinedStr):
            pieces = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    pieces.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    formatted = self._eval_expr(value.value)
                    if value.format_spec is not None:
                        spec = self._eval_expr(value.format_spec)
                        # Avoid a maliciously large width/precision allocation.
                        if len(spec) > 100 or any(int(n) > 10000 for n in re.findall(r"\d+", spec)):
                            raise SafeMathError("Format width or precision is too large.")
                        pieces.append(format(formatted, spec))
                    else:
                        pieces.append(str(formatted))
                else:
                    raise SafeMathError("Unsupported f-string component.")
            return self._check_value("".join(pieces))

        if isinstance(node, ast.ListComp):
            return self._check_value(self._run_comprehension(node, "list"))

        if isinstance(node, ast.SetComp):
            return self._check_value(set(self._run_comprehension(node, "list")))

        if isinstance(node, ast.DictComp):
            pairs = self._run_comprehension(node, "dict")
            return self._check_value(dict(pairs))

        raise SafeMathError(f"Expression '{type(node).__name__}' is not allowed.")

    def _run_comprehension(self, node, kind):
        output = []

        def walk_generator(index):
            if index >= len(node.generators):
                if kind == "dict":
                    output.append((self._eval_expr(node.key), self._eval_expr(node.value)))
                else:
                    output.append(self._eval_expr(node.elt))
                if len(output) > self.MAX_COLLECTION_ITEMS:
                    raise SafeMathError("Comprehension result is too large.")
                return

            generator = node.generators[index]
            if generator.is_async:
                raise SafeMathError("Async comprehensions are not allowed.")
            iterable = self._materialize_iterable(self._eval_expr(generator.iter))
            for item in iterable:
                self._consume_iterations()
                self._assign_target(generator.target, item)
                if all(self._truthy(self._eval_expr(cond)) for cond in generator.ifs):
                    walk_generator(index + 1)

        walk_generator(0)
        return output

    def _eval_slice(self, node):
        if isinstance(node, ast.Slice):
            lower = self._eval_expr(node.lower) if node.lower is not None else None
            upper = self._eval_expr(node.upper) if node.upper is not None else None
            step = self._eval_expr(node.step) if node.step is not None else None
            return slice(lower, upper, step)
        return self._eval_expr(node)

    # ------------------------------------------------------------------
    # Operators and assignment
    # ------------------------------------------------------------------
    def _apply_binop(self, op, left, right):
        if isinstance(op, ast.Add):
            result = left + right
        elif isinstance(op, ast.Sub):
            result = left - right
        elif isinstance(op, ast.Mult):
            self._guard_sequence_repeat(left, right)
            self._guard_numeric_operation(left, right)
            result = left * right
        elif isinstance(op, ast.Div):
            result = left / right
        elif isinstance(op, ast.FloorDiv):
            result = left // right
        elif isinstance(op, ast.Mod):
            result = left % right
        elif isinstance(op, ast.Pow):
            self._guard_numeric_operation(left, right, power=True)
            result = left ** right
        elif isinstance(op, ast.BitAnd):
            result = left & right
        elif isinstance(op, ast.BitOr):
            result = left | right
        elif isinstance(op, ast.BitXor):
            result = left ^ right
        elif isinstance(op, ast.LShift):
            if not isinstance(right, int) or right < 0 or right > self.MAX_SHIFT:
                raise SafeMathError("Left shift amount is outside the allowed range.")
            if isinstance(left, int) and left.bit_length() + right > self.MAX_INT_BITS:
                raise SafeMathError("Shift would produce an oversized integer.")
            result = left << right
        elif isinstance(op, ast.RShift):
            if not isinstance(right, int) or right < 0 or right > self.MAX_SHIFT:
                raise SafeMathError("Right shift amount is outside the allowed range.")
            result = left >> right
        else:
            raise SafeMathError(f"Operator '{type(op).__name__}' is not allowed.")
        return self._check_value(result)

    def _apply_compare(self, op, left, right):
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        raise SafeMathError(f"Comparison '{type(op).__name__}' is not allowed.")

    def _guard_sequence_repeat(self, left, right):
        sequence = None
        count = None
        if isinstance(left, (str, list, tuple)) and isinstance(right, int):
            sequence, count = left, right
        elif isinstance(right, (str, list, tuple)) and isinstance(left, int):
            sequence, count = right, left
        if sequence is not None and count is not None:
            if count < 0:
                return
            if len(sequence) * count > self.MAX_COLLECTION_ITEMS:
                raise SafeMathError("Repeated sequence would be too large.")

    def _assign_target(self, target, value):
        value = self._check_value(value)
        if isinstance(target, ast.Name):
            self._validate_name(target.id)
            self.env[target.id] = value
            return

        if isinstance(target, (ast.Tuple, ast.List)):
            try:
                values = list(value)
            except TypeError:
                raise SafeMathError("Cannot unpack a non-iterable value.") from None
            if len(values) != len(target.elts):
                raise SafeMathError("Unpack target/value lengths do not match.")
            for child, child_value in zip(target.elts, values):
                self._assign_target(child, child_value)
            return

        if isinstance(target, ast.Subscript):
            container = self._eval_expr(target.value)
            if not isinstance(container, (list, dict)):
                raise SafeMathError("Subscript assignment is only allowed on local lists/dicts.")
            index = self._eval_slice(target.slice)
            try:
                container[index] = value
            except Exception as ex:
                raise SafeMathError(f"Subscript assignment error: {ex}") from None
            self._check_value(container)
            return

        raise SafeMathError("Only variables, unpacking targets, and list/dict items can be assigned.")

    def _load_target(self, target):
        if isinstance(target, ast.Name):
            return self._eval_expr(target)
        if isinstance(target, ast.Subscript):
            return self._eval_expr(target)
        raise SafeMathError("Augmented assignment target is not supported.")

    def _materialize_iterable(self, value):
        if isinstance(value, _SafeModule) or isinstance(value, _SafeCallable):
            raise SafeMathError("That object cannot be iterated.")
        try:
            iterator = iter(value)
        except TypeError:
            raise SafeMathError("Value is not iterable.") from None
        return iterator

    @staticmethod
    def _truthy(value):
        return bool(value)


class MathEvaluatorNode:
    DESCRIPTION = (
        "Evaluate restricted Python-style math expressions. Optional w/x float and y/z integer sockets "
        "provide inputs; assign a and b to obtain both float and integer outputs."
    )
    OUTPUT_TOOLTIPS = (
        "Variable a converted to a float.",
        "Variable b converted to a float.",
        "Variable a converted to an integer (truncates toward zero).",
        "Variable b converted to an integer (truncates toward zero).",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expressions": ("STRING", {
                    "multiline": True,
                    "default": "a = w + x\nb = y + z",
                    "tooltip": "Write Python-style mathematical statements using w, x, y, z as optional inputs. Set a and b for the four numeric outputs. Errors return zeros."
                }),
            },
            "optional": {
                "w": ("FLOAT", {"forceInput": True, "tooltip": "Optional float w. Defaults to 0.0 when disconnected."}),
                "x": ("FLOAT", {"forceInput": True, "tooltip": "Optional float x. Defaults to 0.0 when disconnected."}),
                "y": ("INT", {"forceInput": True, "tooltip": "Optional integer y. Defaults to 0 when disconnected."}),
                "z": ("INT", {"forceInput": True, "tooltip": "Optional integer z. Defaults to 0 when disconnected."}),
            },
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "INT", "INT")
    RETURN_NAMES = ("a", "b", "a", "b")
    FUNCTION = "evaluate"
    CATEGORY = "SBL"

    def evaluate(self, expressions, w=None, x=None, y=None, z=None):
        variables = {
            "w": w if w is not None else 0.0,
            "x": x if x is not None else 0.0,
            "y": y if y is not None else 0,
            "z": z if z is not None else 0,
            "a": 0.0,
            "b": 0,
        }

        try:
            interpreter = SafeMathInterpreter(initial_variables=variables)
            env = interpreter.run(expressions)

            a_result_float = float(env.get("a", 0.0))
            b_result_float = float(env.get("b", 0.0))
            a_result_int = int(env.get("a", 0))
            b_result_int = int(env.get("b", 0))

        except Exception as ex:
            print(f"MathEvaluator Error: {ex}")
            a_result_float = 0.0
            b_result_float = 0.0
            a_result_int = 0
            b_result_int = 0

        return (a_result_float, b_result_float, a_result_int, b_result_int)
