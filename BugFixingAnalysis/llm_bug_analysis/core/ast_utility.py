from __future__ import annotations
import ast
from pathlib import Path

from .logger import log


class ASTUtils:
    """Utilities for parsing and analyzing Python AST."""

    @staticmethod
    def parse_file(file_path: Path) -> tuple[ast.Module, list[str]] | None:
        """Parse a Python file into AST nodes and lines."""
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")

            if not content.strip():
                log(f"      Skipping empty file: {file_path}")
                return None

            tree = ast.parse(content, filename=str(file_path))
            lines = content.split("\n")
            return tree, lines

        except SyntaxError as e:
            log(f"      Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            log(f"      Parse error in {file_path}: {e}")
            return None

    @staticmethod
    def parse_string(content: str, filename: str) -> ast.Module | None:
        """Parse Python code from string."""
        try:
            if not content.strip():
                return None
            return ast.parse(content, filename=filename)

        except SyntaxError as e:
            log(f"      Syntax error in {filename}: {e}")
            return None
        except Exception as e:
            log(f"      Parse error in {filename}: {e}")
            return None

    @staticmethod
    def get_classes(tree: ast.Module) -> list[ast.ClassDef]:
        """Get all class definitions from AST."""
        return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    @staticmethod
    def get_functions(
        tree: ast.Module,
        exclude_class_methods: bool = False,
        include_async: bool = True,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Get all function definitions from AST."""

        func_types: tuple[type, ...] = (ast.FunctionDef,)
        if include_async:
            func_types = (ast.FunctionDef, ast.AsyncFunctionDef)

        functions = [node for node in ast.walk(tree) if isinstance(node, func_types)]

        if exclude_class_methods:
            class_methods = set()
            for cls in ASTUtils.get_classes(tree):
                for item in cls.body:
                    if isinstance(item, func_types):
                        class_methods.add(item)

            functions = [f for f in functions if f not in class_methods]

        return functions

    @staticmethod
    def get_qualified_name(node: ast.AST) -> str:
        """Get qualified name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # recursive build
            base = ASTUtils.get_qualified_name(node.value)
            return f"{base}.{node.attr}"
        else:
            try:
                return ast.unparse(node)
            except Exception:
                return str(type(node).__name__)

    @staticmethod
    def find_parent_class(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module
    ) -> ast.ClassDef | None:
        """Find the class that contains the function."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if func_node in node.body:
                    return node
        return None

    @staticmethod
    def get_function_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Get function parameter names."""
        return [arg.arg for arg in node.args.args]

    @staticmethod
    def get_base_classes(node: ast.ClassDef) -> list[str]:
        """Get base class names."""
        return [ASTUtils.get_qualified_name(base) for base in node.bases]

    @staticmethod
    def get_function_calls(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Find all function calls inside a function."""

        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        # no duplicates, preserve order
        return list(dict.fromkeys(calls))
