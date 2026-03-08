from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from desktop.widgets.panel import GlassPanel
from desktop.widgets.form_widgets import (
    FormRow,
    StyledTextInput,
    StyledSpinner,
    StyledButton,
)
from desktop import theme


class EditorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        main_layout = BoxLayout(
            orientation="horizontal", padding=dp(20), spacing=dp(20)
        )

        # ═══════════════════════════════════════════════
        # LEFT SIDEBAR (fixed 320dp width, scrollable)
        # ═══════════════════════════════════════════════
        left_sidebar = ScrollView(size_hint_x=None, width=dp(320))
        left_content = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(16)
        )
        left_content.bind(minimum_height=left_content.setter("height"))

        # — Project Source Panel —
        source_panel = GlassPanel(title="Project Source", size_hint_y=None)
        source_panel.bind(minimum_height=source_panel.setter("height"))

        url_input = StyledTextInput(
            text="", hint_text="https://www.youtube.com/watch?v=..."
        )
        source_panel.add_widget(FormRow("YouTube URL", url_input))

        browser_spinner = StyledSpinner(
            text="None (No login)",
            values=["None (No login)", "Chrome", "Edge", "Firefox", "Brave", "Opera"],
        )
        source_panel.add_widget(FormRow("Browser (Cookies)", browser_spinner))

        mode_spinner = StyledSpinner(
            text="Scan heatmap",
            values=[
                "Scan heatmap (Most Replayed)",
                "AI Analysis (Transcript)",
                "Combined (Heatmap + AI)",
                "Custom start/end (manual)",
            ],
        )
        source_panel.add_widget(FormRow("Mode", mode_spinner))
        left_content.add_widget(source_panel)

        # — Controls Panel —
        controls_panel = GlassPanel(title="Controls", size_hint_y=None)
        controls_panel.bind(minimum_height=controls_panel.setter("height"))

        scan_btn = StyledButton(text="Scan Heatmap", variant="primary_gradient")
        clip_btn = StyledButton(text="Create Clips", variant="secondary_solid")

        controls_box = BoxLayout(
            orientation="vertical", spacing=dp(8), size_hint_y=None
        )
        controls_box.bind(minimum_height=controls_box.setter("height"))
        controls_box.add_widget(scan_btn)
        controls_box.add_widget(clip_btn)

        help_text = Label(
            text="Scan = find heatmap peaks.\nCreate = process clips.",
            font_name=theme.FONT_FAMILY,
            font_size="11sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.6),
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
        )
        help_text.bind(size=help_text.setter("text_size"))
        controls_box.add_widget(help_text)

        controls_panel.add_widget(controls_box)
        left_content.add_widget(controls_panel)

        left_sidebar.add_widget(left_content)
        main_layout.add_widget(left_sidebar)

        # ═══════════════════════════════════════════════
        # CENTER WORKSPACE (flex-fill, scrollable)
        # ═══════════════════════════════════════════════
        center_workspace = ScrollView()
        center_content = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(16)
        )
        center_content.bind(minimum_height=center_content.setter("height"))

        # — Segments Panel —
        seg_panel = GlassPanel(title="Segments", size_hint_y=None, height=dp(260))
        empty_label = Label(
            text="No segments yet.\nClick Scan Heatmap to begin.",
            font_name=theme.FONT_FAMILY,
            font_size="14sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.6),
            halign="center",
            valign="middle",
        )
        empty_label.bind(size=empty_label.setter("text_size"))
        seg_panel.add_widget(empty_label)
        center_content.add_widget(seg_panel)

        # — Bottom row: Progress Tracker + Publishing Metadata —
        bottom_grid = BoxLayout(
            orientation="horizontal", spacing=dp(16), size_hint_y=None, height=dp(200)
        )

        tracker_panel = GlassPanel(title="Progress Tracker")
        tracker_empty = Label(
            text="Waiting for commands...",
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.5),
        )
        tracker_panel.add_widget(tracker_empty)
        bottom_grid.add_widget(tracker_panel)

        meta_panel = GlassPanel(title="Publishing Metadata")
        meta_empty = Label(
            text="Metadata will appear here",
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.5),
        )
        meta_panel.add_widget(meta_empty)
        bottom_grid.add_widget(meta_panel)

        center_content.add_widget(bottom_grid)

        # — Clip Gallery —
        gallery_panel = GlassPanel(
            title="Clip Gallery", size_hint_y=None, height=dp(240)
        )
        gallery_label = Label(
            text="No clips found.\nProcess segments to generate clips.",
            font_name=theme.FONT_FAMILY,
            font_size="14sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.6),
            halign="center",
            valign="middle",
        )
        gallery_label.bind(size=gallery_label.setter("text_size"))
        gallery_panel.add_widget(gallery_label)
        center_content.add_widget(gallery_panel)

        center_workspace.add_widget(center_content)
        main_layout.add_widget(center_workspace)

        self.add_widget(main_layout)
