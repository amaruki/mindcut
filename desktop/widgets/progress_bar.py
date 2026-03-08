from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from .. import theme


class GradientProgressBar(BoxLayout):
    def __init__(self, text="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(24)
        self.spacing = dp(6)

        # Track
        self.track = Widget(size_hint_y=None, height=dp(6))
        with self.track.canvas.before:
            Color(*theme.hex_to_rgba(theme.FG, 0.05))
            self.track_bg = RoundedRectangle(
                pos=self.track.pos, size=self.track.size, radius=[dp(3)]
            )

            self.fill_color = Color(*theme.hex_to_rgba(theme.ACCENT))
            self.fill_rect = RoundedRectangle(
                pos=self.track.pos, size=(0, self.track.height), radius=[dp(3)]
            )

        self.track.bind(pos=self._update_rect, size=self._update_rect)
        self.add_widget(self.track)

        # Label
        self.label = Label(
            text=text,
            font_name=theme.FONT_FAMILY,
            font_size="12sp",
            color=theme.hex_to_rgba(theme.FG_MUTED),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(14),
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)

        self.progress = 0

    def _update_rect(self, *args):
        self.track_bg.pos = self.track.pos
        self.track_bg.size = self.track.size
        self.fill_rect.pos = self.track.pos
        self.fill_rect.size = (self.track.width * self.progress, self.track.height)

    def set_progress(self, percent, text=None):
        self.progress = max(0.0, min(1.0, percent))
        if self.track.width > 0:
            self.fill_rect.size = (self.track.width * self.progress, self.track.height)
        if text is not None:
            self.label.text = text
