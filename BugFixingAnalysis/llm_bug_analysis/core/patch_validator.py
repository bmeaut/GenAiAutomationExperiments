import re
import difflib
from pathlib import Path
from typing import Any
import git

from core.logger import log


class PatchValidator:
    """Validates patches and provides failure analysis."""

    def __init__(self, repo_path: Path, repo: git.Repo | None):
        self.repo_path = Path(repo_path)
        self.repo = repo

    def validate_patch(self, patch_file_path: Path) -> dict[str, Any]:
        """Validate patch and return detailed analysis."""
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "patch_content": "",
            "analysis": {},
            "file_analysis": {},
        }

        try:
            content = patch_file_path.read_text(encoding="utf-8")
            result["patch_content"] = content

            if not content.strip():
                result["errors"].append("Empty patch")
                return result

            hunks = self._parse_hunks(content)
            result["file_analysis"] = hunks

            self._check_files(hunks, result)
            self._dry_run(patch_file_path, result)

            return result

        except Exception as e:
            result["errors"].append(f"Validation failed: {str(e)}")
            return result

    def _check_files(self, hunks: dict[str, list[dict]], result: dict):
        """Check if hunks match actual file content."""
        for path, changes in hunks.items():
            full_path = self.repo_path / path

            if not full_path.exists():
                result["errors"].append(f"File not found: {path}")
                continue

            current = full_path.read_text(encoding="utf-8").splitlines(keepends=True)

            for hunk in changes:
                analysis = self._check_hunk(current, hunk)
                hunk["analysis"] = analysis

    def _dry_run(self, patch_path: Path, result: dict):
        """Try git apply --check."""
        if not self.repo:
            result["warnings"].append("No git repo for dry run")
            return

        try:
            self.repo.git.apply(["--check", "--verbose", str(patch_path)])
            result["valid"] = True
            result["analysis"]["dry_run"] = "PASSED"
        except git.GitCommandError as e:
            result["errors"].append(f"Dry run failed: {e.stderr}")
            result["analysis"]["dry_run"] = "FAILED"
            result["analysis"]["git_error"] = str(e.stderr)

    def _parse_hunks(self, content: str) -> dict[str, list[dict]]:
        """Parse patch into hunks per file."""
        files: dict[str, list[dict]] = {}
        current = None
        lines = content.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith("---"):
                source = line[4:].strip()
                if source.startswith("a/"):
                    source = source[2:]

            elif line.startswith("+++"):
                target = line[4:].strip()
                if target.startswith("b/"):
                    target = target[2:]
                current = target
                files[current] = []

            elif line.startswith("@@") and current:
                parsed = self._parse_single_hunk(lines, i)
                if parsed:
                    files[current].append(parsed["data"])
                    i = parsed["next_index"]
                    continue

            i += 1

        return files

    def _parse_single_hunk(self, lines: list[str], idx: int) -> dict | None:
        """Parse one hunk starting at @@"""
        line = lines[idx]

        # @@ -old_start,old_count +new_start,new_count @@
        match = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", line)
        if not match:
            return None

        hunk = {
            "old_start": int(match.group(1)),
            "old_count": int(match.group(2)) if match.group(2) else 1,
            "new_start": int(match.group(3)),
            "new_count": int(match.group(4)) if match.group(4) else 1,
            "context_before": [],
            "removals": [],
            "additions": [],
            "context_after": [],
        }

        # parse hunk body
        i = idx + 1
        in_changes = False

        while i < len(lines) and not lines[i].startswith("@@"):
            chunk = lines[i]

            if chunk.startswith(" "):
                # context line
                if not in_changes:
                    hunk["context_before"].append(chunk[1:])
                else:
                    hunk["context_after"].append(chunk[1:])

            elif chunk.startswith("-"):
                hunk["removals"].append(chunk[1:])
                in_changes = True

            elif chunk.startswith("+"):
                hunk["additions"].append(chunk[1:])
                in_changes = True

            i += 1

        return {"data": hunk, "next_index": i}

    def _check_hunk(self, file_lines: list[str], hunk: dict) -> dict:
        """Check if hunk matches file and suggest fixes."""
        result = {
            "context_match": False,
            "line_range_valid": False,
            "suggested_location": None,
            "issues": [],
        }

        start = hunk["old_start"] - 1  # 0 indexed
        end = start + hunk["old_count"]

        # check bounds
        if start < 0 or end > len(file_lines):
            result["issues"].append(
                f"Range {start}-{end} exceeds file {len(file_lines)}"
            )
            return result

        result["line_range_valid"] = True

        # check if context matches
        expected = hunk["context_before"] + hunk["removals"] + hunk["context_after"]
        actual = [line.rstrip("\n\r") for line in file_lines[start:end]]

        similarity = difflib.SequenceMatcher(None, expected, actual).ratio()

        if similarity > 0.8:
            result["context_match"] = True
        else:
            result["issues"].append(f"Context similarity only {similarity:.0%} similar")

            # try to find better spot
            better = self._find_match(file_lines, hunk)
            if better:
                result["suggested_location"] = better

        return result

    def _find_match(self, file_lines: list[str], hunk: dict) -> int | None:
        """Find better location using fuzzy matching."""
        pattern = hunk["context_before"] + hunk["removals"]
        if not pattern:
            return None

        best_score = 0.0
        best_line = None

        # search ±20 lines around expected location
        start = max(0, hunk["old_start"] - 20)
        end = min(len(file_lines), hunk["old_start"] + 20)

        for i in range(start, end - len(pattern) + 1):
            candidate = [
                line.rstrip("\n\r") for line in file_lines[i : i + len(pattern)]
            ]
            score = difflib.SequenceMatcher(None, pattern, candidate).ratio()

            if score > best_score and score > 0.7:
                best_score = score
                best_line = i + 1  # 1-indexed

        return best_line
