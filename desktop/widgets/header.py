from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, BoxShadow
from kivy.metrics import dp
from .. import theme


class NavButton(ButtonBehavior, Label):
    def __init__(self, text, target_screen, is_active=False, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.target_screen = target_screen
        self.is_active = is_active
        self.color = theme.hex_to_rgba(theme.FG if is_active else theme.FG_MUTED)
        self.font_name = theme.FONT_FAMILY
        self.font_size = "14sp"
        self.bold = is_active
        if is_active:
            self.color = theme.hex_to_rgba(theme.FG)
        else:
            self.color = theme.hex_to_rgba(theme.FG_MUTED)

    def on_state(self, instance, value):
        if not self.is_active:
            if value == "down":
                self.color = theme.hex_to_rgba(theme.FG)
            else:
                self.color = theme.hex_to_rgba(theme.FG_MUTED)


class HeaderBar(BoxLayout):
    def __init__(self, current_screen="editor_screen", on_navigate=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(56)
        self.padding = [dp(24), 0]
        self.spacing = dp(20)
        self.on_navigate_cb = on_navigate

        with self.canvas.before:
            Color(*theme.hex_to_rgba(theme.BG_HEADER, 0.98))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])

            Color(0, 0, 0, 0.6)
            self.shadow = BoxShadow(
                pos=(self.x, self.y - 5),
                size=(self.width, 5),
                blur_radius=20,
                spread_radius=[5, 5],
            )

            # Bottom border line
            Color(1, 1, 1, 0.06)
            self.border_rect = RoundedRectangle(
                pos=self.pos, size=(self.width, 1), radius=[0]
            )

        self.bind(pos=self.update_rect, size=self.update_rect)

        # Brand
        brand_box = BoxLayout(orientation="horizontal", size_hint_x=None, width=dp(100))
        brand1 = Label(
            text="Mind",
            font_name=theme.FONT_FAMILY,
            font_size="18sp",
            color=theme.hex_to_rgba(theme.FG),
            bold=True,
            size_hint_x=None,
            width=dp(42),
        )
        brand2 = Label(
            text="Cut",
            font_name=theme.FONT_FAMILY,
            font_size="18sp",
            color=theme.hex_to_rgba(theme.ACCENT),
            bold=True,
            size_hint_x=None,
            width=dp(30),
        )
        brand_box.add_widget(brand1)
        brand_box.add_widget(brand2)
        self.add_widget(brand_box)

        # Nav Links
        nav_box = BoxLayout(
            orientation="horizontal", spacing=dp(12), size_hint_x=None, width=dp(400)
        )
        screens = [
            ("Editor Studio", "editor_screen"),
            ("Upload Manager", "upload_screen"),
            ("Channel Videos", "channel_screen"),
            ("Settings", "settings_screen"),
        ]

        for idx, (title, screen_name) in enumerate(screens):
            is_active = screen_name == current_screen
            btn = NavButton(text=title, target_screen=screen_name, is_active=is_active)
            btn.bind(on_release=self.on_nav_pressed)
            nav_box.add_widget(btn)

            if idx < len(screens) - 1:
                sep = Label(
                    text="|",
                    color=(1, 1, 1, 0.15),
                    size_hint_x=None,
                    width=dp(10),
                )
                nav_box.add_widget(sep)

        self.add_widget(nav_box)

        # Spacer
        self.add_widget(Label())

    def update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.shadow.pos = (self.x, self.y)
        self.shadow.size = (self.width, 5)
        self.border_rect.pos = self.pos
        self.border_rect.size = (self.width, 1)

    def on_nav_pressed(self, instance):
        if self.on_navigate_cb:
            self.on_navigate_cb(instance.target_screen)
