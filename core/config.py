import os

# Automatically load variables from .env if it exists
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# AI Analysis Configuration
AI_API_URL = os.getenv("AI_API_URL", "https://api.openai.com/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_SEGMENT_PROMPT = os.getenv("AI_SEGMENT_PROMPT", "")
AI_METADATA_PROMPT = os.getenv("AI_METADATA_PROMPT", "")

OUTPUT_DIR = "clips"      # Directory where generated clips will be saved
MAX_DURATION = 60         # Maximum duration (in seconds) for each clip
MIN_SCORE = 0.40          # Minimum heatmap intensity score to be considered viral
MAX_CLIPS = 10            # Maximum number of clips to generate per video
MAX_WORKERS = 1           # Number of parallel workers (reserved for future concurrency)
PADDING = 10              # Extra seconds added before and after each detected segment
TOP_HEIGHT = 960          # Height for top section (center content) in split mode
BOTTOM_HEIGHT = 320       # Height for bottom section (facecam) in split mode
USE_SUBTITLE = True       # Enable auto subtitle using Faster-Whisper (4-5x faster)
WHISPER_MODEL = "small"    # Whisper model size: tiny, base, small, medium, large
SUBTITLE_FONT = "Arial"
SUBTITLE_FONTS_DIR = None
SUBTITLE_LOCATION = "bottom"
OUTPUT_RATIO = "9:16"
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
COOKIES_BROWSER = ""      # Browser to use for extracting cookies (e.g., "chrome", "edge")


def set_ratio_preset(preset):
    global OUTPUT_RATIO, OUT_WIDTH, OUT_HEIGHT
    OUTPUT_RATIO = preset
    if preset == "9:16":
        OUT_WIDTH, OUT_HEIGHT = 1080, 1920
        return
    if preset == "1:1":
        OUT_WIDTH, OUT_HEIGHT = 1080, 1080
        return
    if preset == "16:9":
        OUT_WIDTH, OUT_HEIGHT = 1920, 1080
        return
    if preset == "original":
        OUT_WIDTH, OUT_HEIGHT = None, None
        return
    raise ValueError("Invalid ratio preset")


def set_ai_config(api_url=None, model=None, api_key=None, segment_prompt=None, metadata_prompt=None, cookies_browser=None):
    global AI_API_URL, AI_MODEL, AI_API_KEY, AI_SEGMENT_PROMPT, AI_METADATA_PROMPT, COOKIES_BROWSER
    if api_url:
        AI_API_URL = api_url
    if model:
        AI_MODEL = model
    if api_key:
        AI_API_KEY = api_key
    if segment_prompt is not None and str(segment_prompt).strip():
        AI_SEGMENT_PROMPT = str(segment_prompt).strip()
    if metadata_prompt is not None and str(metadata_prompt).strip():
        AI_METADATA_PROMPT = str(metadata_prompt).strip()
    if cookies_browser is not None:
        COOKIES_BROWSER = str(cookies_browser).strip()

def get_cookie_args():
    import os
    base_args = ["--js-runtimes", "node", "--remote-components", "ejs:github"]
    if os.path.exists("cookies.txt"):
        return ["--cookies", "cookies.txt"] + base_args
    if COOKIES_BROWSER:
        if COOKIES_BROWSER.lower().endswith(".txt"):
            return ["--cookies", COOKIES_BROWSER] + base_args
        return ["--cookies-from-browser", COOKIES_BROWSER] + base_args
    return []


# ---------- AI URL & Model Helpers ----------

_resolved_chat_url = None


def get_ai_chat_url():
    """
    Return the full chat completions URL.
    If AI_API_URL already ends with /chat/completions, use as-is.
    Otherwise, append /chat/completions automatically.
    """
    global _resolved_chat_url
    if _resolved_chat_url:
        return _resolved_chat_url

    url = AI_API_URL.rstrip("/")
    if url.endswith("/chat/completions"):
        _resolved_chat_url = url
    else:
        _resolved_chat_url = url + "/chat/completions"
        print(f"INFO AI chat URL resolved to: {_resolved_chat_url}")
    return _resolved_chat_url


_discovered_model = None
_model_checked = False


def discover_ai_model():
    """
    Return the AI model to use.
    If AI_MODEL is set, use it. Otherwise, query /models endpoint
    to discover the first available model.
    """
    global _discovered_model, _model_checked
    if _model_checked:
        return _discovered_model or AI_MODEL
    _model_checked = True

    # If user explicitly set a model, use it
    if AI_MODEL and AI_MODEL != "gpt-4":
        _discovered_model = AI_MODEL
        return _discovered_model

    # Try to discover models from API
    import requests
    base_url = AI_API_URL.rstrip("/")
    # Strip /chat/completions if present to get base
    if base_url.endswith("/chat/completions"):
        base_url = base_url[:-len("/chat/completions")]
    models_url = base_url + "/models"

    try:
        resp = requests.get(models_url, headers={
            "Authorization": f"Bearer {AI_API_KEY}" if AI_API_KEY else "",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        if models:
            # Pick the first model
            model_id = models[0].get("id", "")
            if model_id:
                _discovered_model = model_id
                print(f"INFO Auto-discovered AI model: {model_id} (from {len(models)} available)")
                return _discovered_model
    except Exception as e:
        print(f"INFO Could not discover models from {models_url}: {e}")

    _discovered_model = AI_MODEL
    return _discovered_model
