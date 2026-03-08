import os
import json
from core import config

SETTINGS_FILE = "desktop_settings.json"

DEFAULT_SETTINGS = {
    "ratio": "9:16",
    "crop": "default",
    "padding": "10",
    "max_clips": "6",
    "subtitle": "n",
    "whisper_model": "small",
    "subtitle_font_select": "Plus Jakarta Sans",
    "subtitle_font_custom": "",
    "subtitle_location": "bottom",
    "subtitle_fontsdir": "fonts",
    "hook_enabled": "n",
    "hook_voice": "en-US-GuyNeural",
    "hook_voice_rate": "+15%",
    "hook_voice_pitch": "+5Hz",
    "hook_font_size": "72",
    "ai_api_url": "https://api.openai.com/v1/chat/completions",
    "ai_model": "gpt-4o",
    "ai_api_key": "",
    "ai_prompt": "",
    "ai_metadata_prompt": "",
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return settings


def save_settings(new_settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=2)
        apply_to_core(new_settings)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def apply_to_core(settings):
    """Applies loaded settings to the actual `core.config` module so backend logic uses them."""
    # Ratio
    config.set_ratio_preset(settings.get("ratio", "9:16"))

    # Int properties
    try:
        config.PADDING = int(settings.get("padding", 10))
    except (ValueError, TypeError):
        pass
    try:
        config.MAX_CLIPS = int(settings.get("max_clips", 6))
    except (ValueError, TypeError):
        pass

    # Subtitles
    config.USE_SUBTITLE = settings.get("subtitle", "n") == "y"
    config.WHISPER_MODEL = settings.get("whisper_model", "small")
    font_choice = settings.get("subtitle_font_select", "Plus Jakarta Sans")
    if font_choice == "custom" and settings.get("subtitle_font_custom"):
        config.SUBTITLE_FONT = settings.get("subtitle_font_custom")
    else:
        config.SUBTITLE_FONT = font_choice
    config.SUBTITLE_LOCATION = settings.get("subtitle_location", "bottom")
    config.SUBTITLE_FONTS_DIR = settings.get("subtitle_fontsdir", "fonts")

    # Hook
    config.HOOK_ENABLED = settings.get("hook_enabled", "n") == "y"
    config.HOOK_VOICE = settings.get("hook_voice", "en-US-GuyNeural")
    config.HOOK_VOICE_RATE = settings.get("hook_voice_rate", "+15%")
    config.HOOK_VOICE_PITCH = settings.get("hook_voice_pitch", "+5Hz")
    try:
        config.HOOK_FONT_SIZE = int(settings.get("hook_font_size", 72))
    except (ValueError, TypeError):
        pass

    # AI Config
    config.set_ai_config(
        api_url=settings.get("ai_api_url"),
        model=settings.get("ai_model"),
        api_key=settings.get("ai_api_key"),
        segment_prompt=settings.get("ai_prompt"),
        metadata_prompt=settings.get("ai_metadata_prompt"),
    )


# Initialize on import
apply_to_core(load_settings())
