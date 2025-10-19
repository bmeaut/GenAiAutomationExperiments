import os
from pathlib import Path
from dotenv import load_dotenv
from github import Github


class GitHubClient:
    """GitHub API authentication and client creation."""

    _instance: Github | None = None

    @classmethod
    def get_client(cls) -> Github:
        """Get GitHub API client (singleton)."""
        if cls._instance is None:
            token = cls._load_token_from_env()
            if not token:
                raise ValueError(
                    "GitHub token not found! Set GITHUB_TOKEN in .env file."
                )

            cls._instance = Github(token)

        return cls._instance

    @staticmethod
    def _load_token_from_env() -> str | None:
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"

        load_dotenv(dotenv_path=env_path)
        return os.getenv("GITHUB_TOKEN")

    @classmethod
    def reset(cls) -> None:
        # for testing
        cls._instance = None
