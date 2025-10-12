import os
import lizard
import complexipy
from typing import Callable, Dict, Any


# using type hints because Pylance complained (probably for a reason)
def analyze_files(
    repo_path: str, filenames: list[str], log_callback: Callable[[str], None]
) -> dict[str, Any]:
    """
    Analyzes a list of Python files for a suite of code quality metrics.
    """
    total_cc = 0
    total_cognitive = 0
    total_params = 0
    total_tokens = 0
    function_count = 0

    # filter for valid Python file paths.
    py_files = [f for f in filenames if f and f.endswith(".py")]

    for filename in py_files:
        full_path = os.path.join(repo_path, filename)
        try:
            file_cc = 0
            file_cognitive = 0
            file_params = 0
            file_tokens = 0
            file_func_count = 0
            # lizard for metrics except cognitive complexity
            lizard_analyzer = lizard.FileAnalyzer(lizard.get_extensions([]))
            lizard_result = lizard_analyzer(full_path)
            for func in lizard_result.function_list:
                file_func_count += 1
                file_cc += func.cyclomatic_complexity
                file_params += len(func.parameters)
                file_tokens += func.token_count

            # complexipy for cognitive complexity
            complexipy_result = complexipy.file_complexity(full_path)
            file_cognitive += complexipy_result.complexity

            # if all analyses succeeded, add temporary values to totals
            total_cc += file_cc
            total_cognitive += file_cognitive
            total_params += file_params
            total_tokens += file_tokens
            function_count += file_func_count

        except Exception as e:
            log_callback(f"    Warning: Could not analyze {filename}. Reason: {e}")

    avg_params = total_params / function_count if function_count > 0 else 0

    return {
        "total_cc": total_cc,
        "total_cognitive": total_cognitive,
        "avg_params": round(avg_params, 2),
        "total_tokens": total_tokens,
    }
