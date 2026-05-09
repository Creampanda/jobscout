from pathlib import Path
from functools import lru_cache
import hashlib

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Loads a prompt file relative to prompts/ directory.

    Example: load_prompt("job_parser/system.md")
    """
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]
