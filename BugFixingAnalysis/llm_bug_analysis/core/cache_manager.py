import json
from pathlib import Path
from typing import Any
from .logger import log

# TODO: move other cache-related functions here


class CacheManager:
    """Manages loading and saving of JSON cache files for pipeline stages."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.cache_dir = self.project_root / ".cache" / "pipeline_stages"

    def load_json_cache(
        self,
        filename: str,
        expected_type: type,
        not_found_msg: str,
        invalid_type_msg: str = "Invalid data format",
        return_on_error: Any = None,
    ) -> Any:
        """Load JSON data from cache."""
        cache_file = self.cache_dir / filename

        if not cache_file.exists():
            log(f"ERROR: {not_found_msg}")
            return return_on_error

        try:
            data = json.loads(cache_file.read_text())

            if not isinstance(data, expected_type):
                log(f"ERROR: {invalid_type_msg}")
                return return_on_error

            log(f"Loaded {len(data)} items from {filename}")
            return data

        except Exception as e:
            log(f"ERROR: Failed to load {filename}: {e}")
            return return_on_error

    def save_json_cache(
        self,
        filename: str,
        data: Any,
        success_msg: str | None = None,
    ) -> bool:
        """Save data to JSON cache file."""
        cache_file = self.cache_dir / filename
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            cache_file.write_text(json.dumps(data, indent=2, default=str))

            if success_msg:
                log(success_msg)
            else:
                log(f"Saved to {cache_file}")

            return True

        except Exception as e:
            log(f"ERROR: Failed to save {filename}: {e}")
            return False
