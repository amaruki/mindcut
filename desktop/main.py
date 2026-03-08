from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
import os

from desktop import theme
from desktop.widgets.header import HeaderBar

from desktop.screens.editor_screen import EditorScreen
from desktop.screens.upload_screen import UploadScreen
from desktop.screens.channel_screen import ChannelScreen
from desktop.screens.settings_screen import SettingsScreen


class MainWrapper(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"

        # Screen Manager
        self.sm = ScreenManager(transition=NoTransition())
        self.sm.add_widget(EditorScreen(name="editor_screen"))
        self.sm.add_widget(UploadScreen(name="upload_screen"))
        self.sm.add_widget(ChannelScreen(name="channel_screen"))
        self.sm.add_widget(SettingsScreen(name="settings_screen"))

        # Header
        self.header = HeaderBar(
            current_screen=self.sm.current, on_navigate=self.navigate
        )
        self.add_widget(self.header)
        self.add_widget(self.sm)

    def navigate(self, screen_name):
        self.sm.current = screen_name
        # Recreate header to show active state
        self.remove_widget(self.header)
        self.header = HeaderBar(
            current_screen=self.sm.current, on_navigate=self.navigate
        )
        self.add_widget(self.header, index=len(self.children))


class MindCutApp(App):
    def build(self):
        self.title = "MindCut Desktop"
        Window.minimum_width = 1200
        Window.minimum_height = 700
        Window.size = (1280, 800)
        Window.clearcolor = theme.hex_to_rgba(theme.BG_APP)

        theme.register_fonts()

        return MainWrapper()


if __name__ == "__main__":
    MindCutApp().run()
