from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.videoplayer import VideoPlayer
from kivy.metrics import dp
from kivy.clock import Clock
from desktop.widgets.panel import GlassPanel
from desktop.widgets.form_widgets import (
    FormRow,
    FormGrid,
    StyledTextInput,
    StyledSpinner,
    StyledButton,
)
from desktop.widgets.clip_card import ClipCard
from desktop import theme
from desktop.services import clip_service, youtube_service


class UploadScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_clip = None

        main_layout = BoxLayout(orientation="horizontal")

        # ═══════════════════════════════════════════════
        # LEFT SIDEBAR (Clips List)
        # ═══════════════════════════════════════════════
        sidebar = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=dp(320),
            padding=dp(16),
            spacing=dp(12),
        )

        sidebar_header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(32)
        )
        sidebar_header.add_widget(
            Label(
                text="Clips Gallery",
                font_name=theme.FONT_FAMILY,
                font_size="15sp",
                bold=True,
                halign="left",
                valign="middle",
                color=theme.hex_to_rgba(theme.FG),
            )
        )
        refresh_btn = StyledButton(
            text="Refresh",
            variant="glass",
            size_hint_x=None,
            width=dp(80),
        )
        refresh_btn.bind(on_release=lambda x: self._load_clips())
        sidebar_header.add_widget(refresh_btn)
        sidebar.add_widget(sidebar_header)

        scroll = ScrollView()
        self.clip_list = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(8)
        )
        self.clip_list.bind(minimum_height=self.clip_list.setter("height"))

        self.clips_empty_label = Label(
            text="No clips found.\nProcess some segments first.",
            font_name=theme.FONT_FAMILY,
            font_size="13sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.6),
            size_hint_y=None,
            height=dp(100),
            halign="center",
            valign="middle",
        )
        self.clips_empty_label.bind(size=self.clips_empty_label.setter("text_size"))
        self.clip_list.add_widget(self.clips_empty_label)

        scroll.add_widget(self.clip_list)
        sidebar.add_widget(scroll)
        main_layout.add_widget(sidebar)

        # ═══════════════════════════════════════════════
        # RIGHT WORKSPACE
        # ═══════════════════════════════════════════════
        workspace = BoxLayout(orientation="horizontal", padding=dp(20), spacing=dp(20))

        # Video Preview area
        self.preview_panel = GlassPanel(title="Preview")
        self.preview_label = Label(
            text="Select a clip from the gallery\nfor preview",
            font_name=theme.FONT_FAMILY,
            font_size="14sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.5),
            halign="center",
            valign="middle",
        )
        self.preview_label.bind(size=self.preview_label.setter("text_size"))
        self.preview_panel.add_widget(self.preview_label)
        workspace.add_widget(self.preview_panel)

        # Metadata Panel
        meta_scroll = ScrollView(size_hint_x=None, width=dp(320))
        meta_content = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(16)
        )
        meta_content.bind(minimum_height=meta_content.setter("height"))

        meta_panel = GlassPanel(title="Publishing Metadata", size_hint_y=None)
        meta_panel.bind(minimum_height=meta_panel.setter("height"))

        # Load accounts for channel spinner
        account_names = ["No accounts linked"]
        try:
            accounts = youtube_service.get_accounts()
            if accounts:
                account_names = [
                    a.get("title", a.get("id", "Unknown")) for a in accounts
                ]
        except Exception:
            pass

        self.channel_spinner = StyledSpinner(
            text=account_names[0], values=account_names
        )
        meta_panel.add_widget(FormRow("YouTube Channel", self.channel_spinner))

        self.title_input = StyledTextInput(text="")
        meta_panel.add_widget(FormRow("Title", self.title_input))

        self.desc_input = StyledTextInput(text="", multiline=True, height=dp(80))
        meta_panel.add_widget(FormRow("Description", self.desc_input))

        self.tags_input = StyledTextInput(text="Shorts, Gaming, Trending")
        meta_panel.add_widget(FormRow("Tags", self.tags_input))

        grid = FormGrid()
        grid.add_widget(
            FormRow(
                "Privacy",
                StyledSpinner(text="Private", values=["Private", "Public", "Unlisted"]),
            )
        )
        grid.add_widget(FormRow("Schedule", StyledTextInput(text="")))
        meta_panel.add_widget(grid)
        meta_content.add_widget(meta_panel)

        # Actions
        actions = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        actions.bind(minimum_height=actions.setter("height"))
        actions.add_widget(
            StyledButton(text="Save Metadata", variant="primary_gradient")
        )
        actions.add_widget(StyledButton(text="Add Hook Intro", variant="glass"))
        actions.add_widget(
            StyledButton(text="Upload to YouTube", variant="primary_solid")
        )
        meta_content.add_widget(actions)

        meta_scroll.add_widget(meta_content)
        workspace.add_widget(meta_scroll)

        main_layout.add_widget(workspace)
        self.add_widget(main_layout)

        # Load clips on next frame
        Clock.schedule_once(lambda dt: self._load_clips(), 0.5)

    def _load_clips(self):
        """Load real clips from the clips/ directory."""
        self.clip_list.clear_widgets()

        try:
            clips = clip_service.get_gallery()
        except Exception as e:
            print(f"Error loading clips: {e}")
            clips = []

        if not clips:
            self.clip_list.add_widget(self.clips_empty_label)
            return

        for clip_data in clips:
            card = ClipCard(clip_data, on_click=self._on_clip_selected)
            self.clip_list.add_widget(card)

    def _on_clip_selected(self, card):
        # Deselect other cards
        for child in self.clip_list.children:
            if isinstance(child, ClipCard) and child != card:
                child.set_selected(False)

        self.selected_clip = card.clip_data

        # Populate basic title from filename
        filename = self.selected_clip.get("filename", "")
        # Remove .mp4 and underscore to spaces
        base_title = filename.rsplit(".", 1)[0].replace("_", " ").title()

        # Check if clip has parent directory context (for multi-clip scans based on original youtube video slug)
        path = self.selected_clip.get("path", "")
        if path:
            import os

            parent = os.path.basename(os.path.dirname(path))
            if parent and parent != "clips":
                base_title = f"{parent.replace('-', ' ').title()} - {base_title}"

        self.title_input.text = base_title
        self.desc_input.text = (
            f"Check out this short clip from {base_title}!\n\n#shorts"
        )
        self.tags_input.text = "Shorts, Highlight"

        # Load Video Preview
        clip_path = self.selected_clip.get("path", "")
        if clip_path:
            self.preview_panel.clear_widgets()

            # Re-add the title bar of GlassPanel (which is part of its layout technically, so we shouldn't clear_widgets blindly without thought. GlassPanel adds child strictly to self.content_box.)
            # Wait, GlassPanel overrides add_widget, clear_widgets is dangerous if it clears the title!
            # Let's cleanly just clear the content_box. Note: add_widget in panel.py forwards to content_box. clear_widgets might not be cleanly forwarded.
            # I'll check first, but assuming we can clear self.preview_panel then add player.

            # Actually a safer way is just to add a player to `self.preview_panel.content_box.clear_widgets()` manually if it's exposed, but let's try direct since Kivy forwards it sometimes.
            # Wait, I will just call `clear_widgets` on `self.preview_panel` and recreate it? No, just keep a reference to a container inside preview_panel.
            player = VideoPlayer(
                source=clip_path, state="play", options={"eos": "loop"}
            )
            self.preview_panel.add_widget(player)
        else:
            self.preview_panel.clear_widgets()
            self.preview_panel.add_widget(self.preview_label)
