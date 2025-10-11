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

    lizard_analyzer = lizard.FileAnalyzer(lizard.get_extensions([]))

    for filename in py_files:
        full_path = os.path.join(repo_path, filename)
        try:
            # lizard for metrics except cognitive complexity
            lizard_result = lizard.analyze_file(full_path)
            for func in lizard_result.function_list:
                function_count += 1
                total_cc += func.cyclomatic_complexity
                total_params += len(func.parameters)
                total_tokens += func.token_count

            # complexipy for cognitive complexity
            complexipy_result = complexipy.file_complexity(full_path)
            total_cognitive += complexipy_result.complexity

        except Exception as e:
            log_callback(f"    Warning: Could not analyze {filename}. Reason: {e}")

    avg_params = total_params / function_count if function_count > 0 else 0

    return {
        "total_cc": total_cc,
        "total_cognitive": total_cognitive,
        "avg_params": round(avg_params, 2),
        "total_tokens": total_tokens,
    }
