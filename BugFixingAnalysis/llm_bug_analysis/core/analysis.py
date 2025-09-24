import os
from radon.visitors import ComplexityVisitor
from typing import Callable  # type hinting


# using type hints because Pylance complained (probably for a reason)
def analyze_files(
    repo_path: str, filenames: list[str], log_callback: Callable[[str], None]
) -> dict[str, int]:
    """
    Analyzes a list of Python files for Cyclomatic and Cognitive Complexity.
    """
    total_cc = 0
    total_cognitive = 0

    # filter for valid Python file paths.
    py_files = [f for f in filenames if f and f.endswith(".py")]

    for filename in py_files:
        full_path = os.path.join(repo_path, filename)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                code = f.read()

            # radon's visitor walks through the raw code
            visitor = ComplexityVisitor.from_code(code)

            has_async_function = False
            for block in visitor.blocks:
                # block is a flat list, accumulate the complexities of all functions/classes
                total_cc += getattr(block, "complexity", 0)

                # radon does not calculate cognitive complexity for async functions.
                if getattr(block, "is_async", False):
                    has_async_function = True
                else:
                    total_cognitive += getattr(block, "cognitive_complexity", 0)

            # If any async functions were found, log a note about the potential data inaccuracy.
            if has_async_function:
                log_callback(
                    "    [Analysis Note] Cognitive complexity may be underestimated as Radon does not analyze async functions."
                )

        except Exception as e:
            log_callback(f"    Warning: Could not analyze {filename}. Reason: {e}")

    return {"total_cc": total_cc, "total_cognitive": total_cognitive}
