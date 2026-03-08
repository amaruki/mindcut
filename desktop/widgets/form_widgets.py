from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from .. import theme


class StyledTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("foreground_color", theme.hex_to_rgba(theme.FG))
        kwargs.setdefault("cursor_color", theme.hex_to_rgba(theme.ACCENT))
        kwargs.setdefault("hint_text_color", theme.hex_to_rgba(theme.FG_MUTED, 0.5))
        kwargs.setdefault("font_name", theme.FONT_FAMILY)
        kwargs.setdefault("font_size", "15sp")
        kwargs.setdefault("padding", [dp(14), dp(12), dp(14), dp(12)])
        kwargs.setdefault("size_hint_y", None)
        if "height" not in kwargs and not kwargs.get("multiline", False):
            kwargs["height"] = dp(46)

        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*theme.hex_to_rgba(theme.FG, 0.08))
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_SM]
            )

        with self.canvas.after:
            self.border_color = Color(1, 1, 1, 0.08)
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

        self.bind(
            pos=self._update_canvas, size=self._update_canvas, focus=self._on_focus
        )

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

    def _on_focus(self, instance, value):
        if value:
            self.border_color.rgba = theme.hex_to_rgba(theme.ACCENT, 0.7)
        else:
            self.border_color.rgba = (1, 1, 1, 0.08)


class StyledSpinner(Spinner):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", theme.hex_to_rgba(theme.FG))
        kwargs.setdefault("font_name", theme.FONT_FAMILY)
        kwargs.setdefault("font_size", "15sp")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("border", (0, 0, 0, 0))
        kwargs.setdefault("option_cls", StyledSpinnerOption)

        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*theme.hex_to_rgba(theme.FG, 0.08))
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_SM]
            )

        with self.canvas.after:
            Color(1, 1, 1, 0.08)
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


class StyledSpinnerOption(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", theme.hex_to_rgba(theme.BG_PANEL))
        kwargs.setdefault("color", theme.hex_to_rgba(theme.FG))
        kwargs.setdefault("font_name", theme.FONT_FAMILY)
        kwargs.setdefault("font_size", "14sp")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(42))
        super().__init__(**kwargs)


class StyledButton(Button):
    def __init__(self, variant="primary_solid", **kwargs):
        self.variant = variant

        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", theme.hex_to_rgba(theme.FG))
        kwargs.setdefault("font_name", theme.FONT_FAMILY)
        kwargs.setdefault("font_size", "15sp")
        kwargs.setdefault("bold", True)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("border", (0, 0, 0, 0))

        super().__init__(**kwargs)

        with self.canvas.before:
            if variant in ("primary_gradient", "primary_solid"):
                self.bg_color = Color(*theme.hex_to_rgba(theme.ACCENT))
                self.color = (1, 1, 1, 1)
            elif variant == "secondary_solid":
                self.bg_color = Color(*theme.hex_to_rgba(theme.FG, 0.12))
            elif variant in ("glass", "ghost"):
                self.bg_color = Color(1, 1, 1, 0.04)
            else:
                self.bg_color = Color(*theme.hex_to_rgba(theme.FG, 0.08))

            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[theme.RADIUS_SM]
            )

        with self.canvas.after:
            if variant in ("glass", "ghost", "secondary_solid"):
                self.border_color_inst = Color(1, 1, 1, 0.1)
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

        self.bind(
            pos=self._update_canvas, size=self._update_canvas, state=self._on_state
        )

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        if hasattr(self, "border_line"):
            self.border_line.rounded_rectangle = (
                self.x,
                self.y,
                self.width,
                self.height,
                theme.RADIUS_SM,
            )

    def _on_state(self, instance, value):
        if self.variant in ("primary_solid", "primary_gradient"):
            if value == "down":
                self.bg_color.rgba = theme.hex_to_rgba(theme.ACCENT_HOVER)
            else:
                self.bg_color.rgba = theme.hex_to_rgba(theme.ACCENT)
        elif self.variant == "secondary_solid":
            if value == "down":
                self.bg_color.rgba = theme.hex_to_rgba(theme.FG, 0.2)
            else:
                self.bg_color.rgba = theme.hex_to_rgba(theme.FG, 0.12)
        elif self.variant in ("glass", "ghost"):
            if value == "down":
                self.bg_color.rgba = (1, 1, 1, 0.08)
            else:
                self.bg_color.rgba = (1, 1, 1, 0.04)


class FormRow(BoxLayout):
    """A label + form widget stacked vertically with proper sizing."""

    def __init__(self, label_text, widget, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.spacing = dp(4)

        lbl = Label(
            text=label_text,
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            color=theme.hex_to_rgba(theme.FG_MUTED),
            bold=True,
            valign="middle",
            halign="left",
            size_hint_y=None,
            height=dp(22),
        )
        lbl.bind(size=lbl.setter("text_size"))
        self.add_widget(lbl)

        # Ensure the widget has size_hint_y=None so it keeps its fixed height
        widget.size_hint_y = None
        self.add_widget(widget)

        # Total height = label + spacing + widget
        self.bind(minimum_height=self.setter("height"))


class FormGrid(GridLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault("cols", 2)
        kwargs.setdefault("spacing", dp(12))
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)
        self.bind(minimum_height=self.setter("height"))
