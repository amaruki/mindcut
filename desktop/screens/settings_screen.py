from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp
from desktop.widgets.panel import GlassPanel
from desktop.widgets.form_widgets import (
    FormRow,
    FormGrid,
    StyledTextInput,
    StyledSpinner,
    StyledButton,
)
from desktop import theme
from desktop.services import settings_service


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._widgets = {}

        # Centered layout
        outer_layout = BoxLayout(orientation="horizontal")
        outer_layout.add_widget(Label(size_hint_x=0.5))  # Spacer

        scroll = ScrollView(size_hint_x=None, width=dp(700))
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(20),
            padding=[0, dp(30)],
        )
        content.bind(minimum_height=content.setter("height"))

        # Header text
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(56))
        title = Label(
            text="Application Settings",
            font_name=theme.FONT_FAMILY,
            font_size="22sp",
            bold=True,
            halign="left",
            valign="bottom",
            color=theme.hex_to_rgba(theme.FG),
            size_hint_y=None,
            height=dp(30),
        )
        title.bind(size=title.setter("text_size"))
        sub = Label(
            text="Configure your default preferences for clip generation and AI features.",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.7),
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(20),
        )
        sub.bind(size=sub.setter("text_size"))
        header.add_widget(title)
        header.add_widget(sub)
        content.add_widget(header)

        # Load saved settings
        settings = settings_service.load_settings()

        # ── Output Formatting ──
        p1 = GlassPanel(title="Output Formatting", size_hint_y=None)
        p1.bind(minimum_height=p1.setter("height"))
        g1 = FormGrid()
        w = StyledSpinner(
            text=self._ratio_display(settings.get("ratio", "9:16")),
            values=["9:16 (Shorts)", "1:1 (Square)", "16:9 (Landscape)", "Original"],
        )
        self._widgets["ratio"] = w
        g1.add_widget(FormRow("Ratio Default", w))

        w = StyledSpinner(
            text=settings.get("crop", "default").title(),
            values=["Default", "Center", "Auto"],
        )
        self._widgets["crop"] = w
        g1.add_widget(FormRow("Crop Target Default", w))

        w = StyledTextInput(text=settings.get("padding", "10"))
        self._widgets["padding"] = w
        g1.add_widget(FormRow("Pad (sec)", w))

        w = StyledTextInput(text=settings.get("max_clips", "6"))
        self._widgets["max_clips"] = w
        g1.add_widget(FormRow("Max clips limit", w))
        p1.add_widget(g1)
        content.add_widget(p1)

        # ── Subtitles & Transcribe ──
        p2 = GlassPanel(title="Subtitles & Transcribe", size_hint_y=None)
        p2.bind(minimum_height=p2.setter("height"))
        g2 = FormGrid()

        w = StyledSpinner(
            text="Yes" if settings.get("subtitle", "n") == "y" else "No",
            values=["Yes", "No"],
        )
        self._widgets["subtitle"] = w
        g2.add_widget(FormRow("Enable Burn-in", w))

        w = StyledSpinner(
            text=settings.get("whisper_model", "small"),
            values=["tiny", "base", "small", "medium", "large"],
        )
        self._widgets["whisper_model"] = w
        g2.add_widget(FormRow("Model", w))

        w = StyledSpinner(
            text=settings.get("subtitle_font_select", "Plus Jakarta Sans"),
            values=["Plus Jakarta Sans", "Arial", "Roboto", "Inter", "custom"],
        )
        self._widgets["subtitle_font_select"] = w
        g2.add_widget(FormRow("Font Face", w))

        w = StyledSpinner(
            text=settings.get("subtitle_location", "bottom"),
            values=["bottom", "top", "center"],
        )
        self._widgets["subtitle_location"] = w
        g2.add_widget(FormRow("Location", w))
        p2.add_widget(g2)

        w = StyledTextInput(text=settings.get("subtitle_fontsdir", "fonts"))
        self._widgets["subtitle_fontsdir"] = w
        p2.add_widget(FormRow("Fonts Directory", w))
        content.add_widget(p2)

        # ── Hook Intro ──
        p3 = GlassPanel(title="Hook Intro", size_hint_y=None)
        p3.bind(minimum_height=p3.setter("height"))
        g3 = FormGrid()

        w = StyledSpinner(
            text="Yes" if settings.get("hook_enabled", "n") == "y" else "No",
            values=["Yes", "No"],
        )
        self._widgets["hook_enabled"] = w
        g3.add_widget(FormRow("Enable Hook Intro", w))

        w = StyledSpinner(
            text=settings.get("hook_voice", "en-US-GuyNeural"),
            values=["en-US-GuyNeural", "en-US-JennyNeural", "en-US-AriaNeural"],
        )
        self._widgets["hook_voice"] = w
        g3.add_widget(FormRow("Hook Voice", w))

        w = StyledTextInput(text=settings.get("hook_voice_rate", "+15%"))
        self._widgets["hook_voice_rate"] = w
        g3.add_widget(FormRow("Voice Speed (Rate)", w))

        w = StyledTextInput(text=settings.get("hook_voice_pitch", "+5Hz"))
        self._widgets["hook_voice_pitch"] = w
        g3.add_widget(FormRow("Voice Pitch", w))
        p3.add_widget(g3)

        w = StyledTextInput(text=settings.get("hook_font_size", "72"))
        self._widgets["hook_font_size"] = w
        p3.add_widget(FormRow("Hook Font Size", w))
        content.add_widget(p3)

        # ── Advanced AI Control ──
        p4 = GlassPanel(title="Advanced AI Control", size_hint_y=None)
        p4.bind(minimum_height=p4.setter("height"))
        g4 = FormGrid()

        w = StyledTextInput(
            text=settings.get(
                "ai_api_url", "https://api.openai.com/v1/chat/completions"
            )
        )
        self._widgets["ai_api_url"] = w
        g4.add_widget(FormRow("API URL", w))

        w = StyledTextInput(text=settings.get("ai_model", "gpt-4o"))
        self._widgets["ai_model"] = w
        g4.add_widget(FormRow("AI Model", w))
        p4.add_widget(g4)

        w = StyledTextInput(text=settings.get("ai_api_key", ""), password=True)
        self._widgets["ai_api_key"] = w
        p4.add_widget(FormRow("API Key", w))

        w = StyledTextInput(
            text=settings.get("ai_prompt", ""),
            multiline=True,
            height=dp(70),
        )
        self._widgets["ai_prompt"] = w
        p4.add_widget(FormRow("Segment Prompt", w))

        w = StyledTextInput(
            text=settings.get("ai_metadata_prompt", ""),
            multiline=True,
            height=dp(70),
        )
        self._widgets["ai_metadata_prompt"] = w
        p4.add_widget(FormRow("Metadata Prompt", w))
        content.add_widget(p4)

        # Save button row
        save_btn_box = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(48)
        )
        save_btn_box.add_widget(Label())  # Spacer
        save_btn = StyledButton(
            text="Save Settings",
            variant="primary_gradient",
            size_hint_x=None,
            width=dp(160),
        )
        save_btn.bind(on_release=self._save_settings)
        save_btn_box.add_widget(save_btn)
        content.add_widget(save_btn_box)

        scroll.add_widget(content)
        outer_layout.add_widget(scroll)
        outer_layout.add_widget(Label(size_hint_x=0.5))  # Spacer

        self.add_widget(outer_layout)

    def _ratio_display(self, val):
        mapping = {
            "9:16": "9:16 (Shorts)",
            "1:1": "1:1 (Square)",
            "16:9": "16:9 (Landscape)",
            "original": "Original",
        }
        return mapping.get(val, val)

    def _ratio_value(self, display):
        mapping = {
            "9:16 (Shorts)": "9:16",
            "1:1 (Square)": "1:1",
            "16:9 (Landscape)": "16:9",
            "Original": "original",
        }
        return mapping.get(display, display)

    def _save_settings(self, *args):
        new_settings = {
            "ratio": self._ratio_value(self._widgets["ratio"].text),
            "crop": self._widgets["crop"].text.lower(),
            "padding": self._widgets["padding"].text,
            "max_clips": self._widgets["max_clips"].text,
            "subtitle": "y" if self._widgets["subtitle"].text == "Yes" else "n",
            "whisper_model": self._widgets["whisper_model"].text,
            "subtitle_font_select": self._widgets["subtitle_font_select"].text,
            "subtitle_location": self._widgets["subtitle_location"].text,
            "subtitle_fontsdir": self._widgets["subtitle_fontsdir"].text,
            "hook_enabled": "y" if self._widgets["hook_enabled"].text == "Yes" else "n",
            "hook_voice": self._widgets["hook_voice"].text,
            "hook_voice_rate": self._widgets["hook_voice_rate"].text,
            "hook_voice_pitch": self._widgets["hook_voice_pitch"].text,
            "hook_font_size": self._widgets["hook_font_size"].text,
            "ai_api_url": self._widgets["ai_api_url"].text,
            "ai_model": self._widgets["ai_model"].text,
            "ai_api_key": self._widgets["ai_api_key"].text,
            "ai_prompt": self._widgets["ai_prompt"].text,
            "ai_metadata_prompt": self._widgets["ai_metadata_prompt"].text,
        }
        success = settings_service.save_settings(new_settings)
        if success:
            print("Settings saved successfully")
