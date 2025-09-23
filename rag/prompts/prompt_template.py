import os


PROMPT_DIR = os.path.dirname(__file__)

_loaded_prompts = {}


def load_prompt(name: str) -> str:
    # Check if already loaded
    cache_key = f"{name}_{os.getenv('PROMPT_LANGUAGE', 'zh')}"
    if cache_key in _loaded_prompts:
        return _loaded_prompts[cache_key]

    # Get language from environment, default to Chinese
    language = os.getenv("PROMPT_LANGUAGE", "zh")

    # Try to load from the specified language directory
    path = os.path.join(PROMPT_DIR, language, f"{name}.md")

    # If not found and not already trying English, fallback to English
    if not os.path.isfile(path) and language != "en":
        path = os.path.join(PROMPT_DIR, "en", f"{name}.md")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt file '{name}.md' not found in either {language}/ or en/ directory.")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        _loaded_prompts[cache_key] = content
        return content
