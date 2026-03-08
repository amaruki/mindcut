from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, BoxShadow, Line
from .. import theme


class ModalPopup(ModalView):
    def __init__(self, title="Modal", content_widget=None, **kwargs):
        kwargs.setdefault("background_color", (0, 0, 0, 0.8))  # backdrop
        kwargs.setdefault("size_hint", (0.9, 0.9))
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)

        # Card Container
        card = BoxLayout(orientation="vertical")
        with card.canvas.before:
            Color(0, 0, 0, 0.8)
            self.shadow = BoxShadow(
                pos=card.pos,
                size=card.size,
                offset=(0, -12),
                blur_radius=40,
                spread_radius=0,
                border_radius=[theme.RADIUS_LG] * 4,
            )
            Color(*theme.hex_to_rgba(theme.BG_PANEL))
            self.card_bg = RoundedRectangle(
                pos=card.pos, size=card.size, radius=[theme.RADIUS_LG]
            )
            Color(1, 1, 1, 0.06)
            self.card_border = Line(
                rounded_rectangle=(
                    card.x,
                    card.y,
                    card.width,
                    card.height,
                    theme.RADIUS_LG,
                ),
                width=1,
            )
        card.bind(pos=self.update_card, size=self.update_card)

        # Top Bar
        top_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="56dp",
            padding=["20dp", 0],
        )
        with top_bar.canvas.before:
            Color(*theme.hex_to_rgba(theme.BORDER))
            self.top_border = RoundedRectangle(
                pos=top_bar.pos, size=(top_bar.width, 1), radius=[0]
            )
        top_bar.bind(pos=self.update_top_bar, size=self.update_top_bar)

        title_lbl = Label(
            text=title,
            font_name=theme.FONT_FAMILY,
            font_size="16sp",
            bold=True,
            color=theme.hex_to_rgba(theme.FG),
            text_size=(None, None),
            halign="left",
            valign="middle",
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        top_bar.add_widget(title_lbl)

        close_btn = Button(
            text="X",
            font_name=theme.FONT_FAMILY,
            font_size="16sp",
            bold=True,
            color=theme.hex_to_rgba(theme.FG_MUTED),
            background_normal="",
            background_color=(0, 0, 0, 0),
            size_hint_x=None,
            width="40dp",
        )
        close_btn.bind(on_release=self.dismiss)
        top_bar.add_widget(close_btn)

        card.add_widget(top_bar)

        # Content Area
        self.modal_body = BoxLayout(padding="20dp")
        if content_widget:
            self.modal_body.add_widget(content_widget)
        card.add_widget(self.modal_body)

        self.add_widget(card)

    def update_card(self, instance, *args):
        self.shadow.pos = instance.pos
        self.shadow.size = instance.size
        self.card_bg.pos = instance.pos
        self.card_bg.size = instance.size
        self.card_border.rounded_rectangle = (
            instance.x,
            instance.y,
            instance.width,
            instance.height,
            theme.RADIUS_LG,
        )

    def update_top_bar(self, instance, *args):
        self.top_border.pos = instance.pos
        self.top_border.size = (instance.width, 1)
