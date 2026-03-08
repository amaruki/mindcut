from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, BoxShadow, Line
from kivy.metrics import dp
from .. import theme


class GlassPanel(BoxLayout):
    """A dark glass-style panel with rounded corners, shadow, and subtle border."""

    def __init__(self, title=None, header_right_widget=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(16)
        self.spacing = dp(10)

        with self.canvas.before:
            # Shadow
            Color(0, 0, 0, 0.35)
            self.shadow = BoxShadow(
                pos=self.pos,
                size=self.size,
                offset=(0, -4),
                blur_radius=20,
                spread_radius=[0, 0],
                border_radius=[theme.RADIUS_MD] * 4,
            )
            # Background fill
            Color(*theme.hex_to_rgba(theme.BG_PANEL, 0.85))
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_MD]
            )
            # Border (drawn in canvas.before, after bg, so it shows on panel
            # but under child widgets — children draw over this)
            Color(1, 1, 1, 0.06)
            self.border_line = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    theme.RADIUS_MD,
                ),
                width=1,
            )

        self.bind(pos=self._update_canvas, size=self._update_canvas)

        # Title header
        if title or header_right_widget:
            header_box = BoxLayout(
                orientation="horizontal", size_hint_y=None, height=dp(24)
            )

            if title:
                title_lbl = Label(
                    text=title,
                    font_name=theme.FONT_FAMILY,
                    font_size="14sp",
                    bold=True,
                    color=theme.hex_to_rgba(theme.FG),
                    valign="middle",
                    halign="left",
                )
                title_lbl.bind(size=title_lbl.setter("text_size"))
                header_box.add_widget(title_lbl)
            else:
                header_box.add_widget(Label())

            if header_right_widget:
                header_box.add_widget(header_right_widget)

            super().add_widget(header_box)

        # Inner content area: size_hint_y=None with minimum_height binding
        # so that children with fixed heights cause this to grow properly
        self.content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        super().add_widget(self.content)

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.shadow.pos = self.pos
        self.shadow.size = self.size
        self.border_line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            theme.RADIUS_MD,
        )

    def add_widget(self, widget, index=0, canvas=None):
        if hasattr(self, "content") and widget is not self.content:
            self.content.add_widget(widget, index, canvas)
        else:
            super().add_widget(widget, index, canvas)
