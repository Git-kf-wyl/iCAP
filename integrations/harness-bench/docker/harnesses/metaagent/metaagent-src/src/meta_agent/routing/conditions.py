"""A bounded expression interpreter. Never evaluates Python code."""

import ast
import operator
from collections.abc import Callable
from typing import Any

_COMPARE: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class Condition:
    def __init__(self, expression: str | None) -> None:
        self.expression = expression
        self.tree: ast.Expression | None = None
        if expression is None:
            return
        if len(expression) > 1024:
            raise ValueError("Condition is too long")
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Invalid condition syntax") from exc
        allowed = (
            ast.Expression,
            ast.BoolOp,
            ast.And,
            ast.Or,
            ast.UnaryOp,
            ast.Not,
            ast.Compare,
            *tuple(_COMPARE),
            ast.Name,
            ast.Load,
            ast.Attribute,
            ast.Subscript,
            ast.Constant,
            ast.List,
            ast.Tuple,
        )
        if len(list(ast.walk(tree))) > 100:
            raise ValueError("Condition is too complex")
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise ValueError("Unsupported condition syntax")
            if isinstance(node, ast.Name) and node.id != "context":
                raise ValueError("Only context may be referenced")
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                raise ValueError("Private attributes are forbidden")
        self.tree = tree

    def matches(self, context: dict[str, Any]) -> bool:
        def visit(node: ast.AST) -> Any:
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                return context
            if isinstance(node, (ast.List, ast.Tuple)):
                return [visit(item) for item in node.elts]
            if isinstance(node, ast.Attribute):
                obj = visit(node.value)
                return obj.get(node.attr) if isinstance(obj, dict) else None
            if isinstance(node, ast.Subscript):
                obj, key = visit(node.value), visit(node.slice)
                return obj.get(key) if isinstance(obj, dict) else obj[key]
            if isinstance(node, ast.UnaryOp):
                return not visit(node.operand)
            if isinstance(node, ast.BoolOp):
                values = (bool(visit(value)) for value in node.values)
                return all(values) if isinstance(node.op, ast.And) else any(values)
            if isinstance(node, ast.Compare):
                left = visit(node.left)
                for op, right_node in zip(node.ops, node.comparators, strict=True):
                    right = visit(right_node)
                    if not _COMPARE[type(op)](left, right):
                        return False
                    left = right
                return True
            raise ValueError("Invalid condition node")

        try:
            return self.tree is None or bool(visit(self.tree.body))
        except (KeyError, IndexError, TypeError, ValueError):
            return False
