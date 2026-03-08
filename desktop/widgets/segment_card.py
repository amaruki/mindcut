from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import AsyncImage
from kivy.graphics import Color, RoundedRectangle, BoxShadow, Line
from kivy.metrics import dp
from .. import theme


class SegmentCard(BoxLayout):
    def __init__(self, segment, on_click=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(76)
        self.padding = dp(12)
        self.spacing = dp(12)
        self.segment = segment
        self.on_click_cb = on_click
        self.is_selected = False

        with self.canvas.before:
            self.bg_color = Color(*theme.hex_to_rgba(theme.FG, 0.04))
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_MD]
            )

        with self.canvas.after:
            self.border_color = Color(1, 1, 1, 0.06)
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

        # Thumbnail Placeholder
        thumb_box = BoxLayout(size_hint_x=None, width=dp(100))
        self.thumb = BoxLayout(size_hint=(1, 1))
        with self.thumb.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            self.thumb_rect = RoundedRectangle(
                pos=self.thumb.pos, size=self.thumb.size, radius=[dp(6)]
            )
        self.thumb.bind(pos=self._update_thumb_rect, size=self._update_thumb_rect)

        # Time overlay
        time_text = f"{self._format_time(segment.get('start', 0))} - {self._format_time(segment.get('end', 0))}"
        self.time_lbl = Label(
            text=time_text,
            font_name=theme.FONT_FAMILY,
            font_size="9sp",
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(54), dp(16)),
            pos_hint={"x": 0.05, "y": 0.05},
        )
        # Small background for time label for readability
        with self.time_lbl.canvas.before:
            Color(0, 0, 0, 0.6)
            self.time_bg = RoundedRectangle(
                pos=self.time_lbl.pos, size=self.time_lbl.size, radius=[dp(3)]
            )

        def _update_time_bg(instance, *args):
            instance.time_bg.pos = instance.pos
            instance.time_bg.size = instance.size

        self.time_lbl.bind(pos=_update_time_bg, size=_update_time_bg)

        self.thumb.add_widget(self.time_lbl)
        thumb_box.add_widget(self.thumb)
        self.add_widget(thumb_box)

        # Main Text
        main_box = BoxLayout(orientation="vertical", padding=[0, dp(2), 0, dp(2)])
        title = segment.get("text", "No description")
        if len(title) > 60:
            title = title[:57] + "..."
        self.title_lbl = Label(
            text=title,
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            bold=True,
            color=theme.hex_to_rgba(theme.FG),
            text_size=(None, None),
            halign="left",
            valign="top",
        )
        self.title_lbl.bind(size=self.title_lbl.setter("text_size"))

        reason = segment.get("reason", "")
        if len(reason) > 50:
            reason = reason[:47] + "..."
        self.reason_lbl = Label(
            text=reason,
            font_name=theme.FONT_FAMILY,
            font_size="11sp",
            color=theme.hex_to_rgba(theme.FG_MUTED),
            text_size=(None, None),
            halign="left",
            valign="top",
        )
        self.reason_lbl.bind(size=self.reason_lbl.setter("text_size"))

        main_box.add_widget(self.title_lbl)
        main_box.add_widget(self.reason_lbl)
        self.add_widget(main_box)

        # Side Score Pill
        score = segment.get("score", 0)
        pill_box = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=dp(40),
            padding=[0, dp(4), 0, 0],
        )
        score_pill = Label(
            text=f"{score:.2f}",
            font_name=theme.FONT_FAMILY,
            font_size="11sp",
            bold=True,
            color=theme.hex_to_rgba(theme.ACCENT),
            size_hint=(None, None),
            size=(dp(40), dp(18)),
            pos_hint={"right": 1.0, "top": 1.0},
        )
        pill_box.add_widget(score_pill)
        pill_box.add_widget(Label())  # Spacer
        self.add_widget(pill_box)

    def _format_time(self, seconds):
        if not isinstance(seconds, (int, float)):
            return "0:00"
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m}:{s:02d}"

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            theme.RADIUS_MD,
        )

    def _update_thumb_rect(self, *args):
        self.thumb_rect.pos = self.thumb.pos
        self.thumb_rect.size = self.thumb.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.toggle_selection()
            if self.on_click_cb:
                self.on_click_cb(self)
            return True
        return super().on_touch_down(touch)

    def toggle_selection(self):
        self.is_selected = not self.is_selected
        if self.is_selected:
            self.border_color.rgba = theme.hex_to_rgba(theme.ACCENT, 0.7)
            self.bg_color.rgba = theme.hex_to_rgba(theme.ACCENT, 0.12)
        else:
            self.border_color.rgba = (1, 1, 1, 0.06)
            self.bg_color.rgba = theme.hex_to_rgba(theme.FG, 0.04)
