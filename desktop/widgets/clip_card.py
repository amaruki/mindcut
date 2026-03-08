from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from .. import theme


class ClipCard(BoxLayout):
    def __init__(self, clip_data, on_click=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(52)
        self.padding = dp(10)
        self.spacing = dp(10)
        self.clip_data = clip_data
        self.on_click_cb = on_click
        self.is_selected = False

        with self.canvas.before:
            self.bg_color = Color(*theme.hex_to_rgba(theme.FG, 0.04))
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_SM]
            )

        with self.canvas.after:
            self.border_color = Color(1, 1, 1, 0.06)
            self.border_line = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    theme.RADIUS_SM,
                ),
                width=1,
            )

        self.bind(pos=self._update_canvas, size=self._update_canvas)

        # Info Box
        info_box = BoxLayout(orientation="vertical")
        filename = clip_data.get("filename", "Unknown")
        # Show parent folder + filename for context
        path = clip_data.get("path", "")
        if path:
            import os

            parent = os.path.basename(os.path.dirname(path))
            if parent and parent != "clips":
                display = f"{parent}/{filename}"
            else:
                display = filename
        else:
            display = filename

        if len(display) > 35:
            display = display[:32] + "..."

        self.title_lbl = Label(
            text=display,
            font_name=theme.FONT_FAMILY,
            font_size="12sp",
            bold=True,
            color=theme.hex_to_rgba(theme.FG),
            halign="left",
            valign="bottom",
            size_hint_y=None,
            height=dp(20),
        )
        self.title_lbl.bind(size=self.title_lbl.setter("text_size"))

        size_str = self._format_size(clip_data.get("size_bytes", 0))
        self.size_lbl = Label(
            text=size_str,
            font_name=theme.FONT_FAMILY,
            font_size="10sp",
            color=theme.hex_to_rgba(theme.FG_MUTED),
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(16),
        )
        self.size_lbl.bind(size=self.size_lbl.setter("text_size"))

        info_box.add_widget(self.title_lbl)
        info_box.add_widget(self.size_lbl)
        self.add_widget(info_box)

    def _format_size(self, size_bytes):
        if not size_bytes:
            return "0 B"
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB"

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            theme.RADIUS_SM,
        )

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.set_selected(True)
            if self.on_click_cb:
                self.on_click_cb(self)
            return True
        return super().on_touch_down(touch)

    def set_selected(self, selected=True):
        self.is_selected = selected
        if self.is_selected:
            self.border_color.rgba = theme.hex_to_rgba(theme.ACCENT, 0.7)
            self.bg_color.rgba = theme.hex_to_rgba(theme.ACCENT, 0.12)
        else:
            self.border_color.rgba = (1, 1, 1, 0.06)
            self.bg_color.rgba = theme.hex_to_rgba(theme.FG, 0.04)
