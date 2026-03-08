import calendar
import datetime
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line
from desktop.widgets.form_widgets import StyledSpinner, StyledButton
from desktop import theme
from desktop.services import youtube_service


class ChannelScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.videos = []
        self.current_year = datetime.date.today().year
        self.current_month = datetime.date.today().month
        self.active_filter = "All"
        self.view_mode = "Calendar"

        main_layout = BoxLayout(orientation="vertical")

        # ── Toolbar ──
        toolbar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            padding=[dp(20), dp(8)],
            spacing=dp(12),
        )

        # Load accounts
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
            text=account_names[0],
            values=account_names,
            size_hint_x=None,
            width=dp(220),
        )
        toolbar.add_widget(self.channel_spinner)

        refresh_btn = StyledButton(
            text="Refresh",
            variant="glass",
            size_hint_x=None,
            width=dp(80),
        )
        refresh_btn.bind(on_release=lambda x: self._load_videos())
        toolbar.add_widget(refresh_btn)

        toolbar.add_widget(Label(size_hint_x=1))  # Spacer

        link_btn = StyledButton(
            text="Link Account",
            variant="primary_gradient",
            size_hint_x=None,
            width=dp(140),
        )
        toolbar.add_widget(link_btn)

        self.view_toggle_btn = StyledButton(
            text="View: Calendar",
            variant="ghost",
            size_hint_x=None,
            width=dp(140),
        )
        # We will implement grid view later if needed, for now just a placeholder
        self.view_toggle_btn.bind(on_release=self._toggle_view_mode)
        toolbar.add_widget(self.view_toggle_btn)

        main_layout.add_widget(toolbar)

        # ── Calendar Navigation ──
        nav_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            padding=[dp(20), dp(6)],
            spacing=dp(8),
        )

        prev_btn = StyledButton(
            text="<",
            variant="glass",
            size_hint_x=None,
            width=dp(40),
        )
        prev_btn.bind(on_release=lambda x: self._change_month(-1))
        nav_bar.add_widget(prev_btn)

        self.month_label = Label(
            text=self._format_month(),
            font_name=theme.FONT_FAMILY,
            font_size="16sp",
            bold=True,
            color=theme.hex_to_rgba(theme.FG),
            size_hint_x=None,
            width=dp(180),
            halign="center",
        )
        self.month_label.bind(size=self.month_label.setter("text_size"))
        nav_bar.add_widget(self.month_label)

        next_btn = StyledButton(
            text=">",
            variant="glass",
            size_hint_x=None,
            width=dp(40),
        )
        next_btn.bind(on_release=lambda x: self._change_month(1))
        nav_bar.add_widget(next_btn)

        today_btn = StyledButton(
            text="Today",
            variant="secondary_solid",
            size_hint_x=None,
            width=dp(70),
        )
        today_btn.bind(on_release=lambda x: self._go_today())
        nav_bar.add_widget(today_btn)

        nav_bar.add_widget(Label(size_hint_x=1))  # Spacer

        # Video count label
        self.count_label = Label(
            text="",
            font_name=theme.FONT_FAMILY,
            font_size="12sp",
            color=theme.hex_to_rgba(theme.FG_MUTED, 0.7),
            size_hint_x=None,
            width=dp(120),
            halign="right",
        )
        self.count_label.bind(size=self.count_label.setter("text_size"))
        nav_bar.add_widget(self.count_label)

        main_layout.add_widget(nav_bar)

        # ── Filter Tabs ──
        self.filter_tabs_container = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            padding=[dp(20), 0, dp(20), dp(10)],
            spacing=dp(10),
        )
        main_layout.add_widget(self.filter_tabs_container)

        # ── Calendar Grid ──
        scroll = ScrollView()
        self.calendar_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(20), dp(10)],
            spacing=dp(2),
        )
        self.calendar_container.bind(
            minimum_height=self.calendar_container.setter("height")
        )

        scroll.add_widget(self.calendar_container)
        main_layout.add_widget(scroll)

        self.add_widget(main_layout)

        # Load on next frame
        Clock.schedule_once(lambda dt: self._load_videos(), 0.5)

    def _format_month(self):
        return datetime.date(self.current_year, self.current_month, 1).strftime("%B %Y")

    def _change_month(self, delta):
        m = self.current_month + delta
        y = self.current_year
        if m > 12:
            m = 1
            y += 1
        elif m < 1:
            m = 12
            y -= 1
        self.current_month = m
        self.current_year = y
        self.month_label.text = self._format_month()
        self._rebuild_calendar()

    def _go_today(self):
        today = datetime.date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.month_label.text = self._format_month()
        self._rebuild_calendar()

    def _load_videos(self):
        """Load channel videos from the YouTube API."""
        try:
            self.videos = youtube_service.list_channel_videos()
        except Exception as e:
            print(f"Error loading videos: {e}")
            self.videos = []

        self._update_filter_tabs()
        self._rebuild_calendar()

    def _toggle_view_mode(self, instance):
        if self.view_mode == "Calendar":
            self.view_mode = "Grid"
            self.view_toggle_btn.text = "View: Grid"
        else:
            self.view_mode = "Calendar"
            self.view_toggle_btn.text = "View: Calendar"
        # Just rebuild calendar for now as Grid isn't fully implemented
        self._rebuild_calendar()

    def _set_active_filter(self, filter_name):
        self.active_filter = filter_name
        self._update_filter_tabs()
        self._rebuild_calendar()

    def _update_filter_tabs(self):
        self.filter_tabs_container.clear_widgets()

        counts = {"All": len(self.videos), "Public": 0, "Unlisted": 0, "Private": 0}
        for v in self.videos:
            privacy = v.get("privacyStatus", "private").capitalize()
            if privacy in counts:
                counts[privacy] += 1

        filters = ["All", "Public", "Unlisted", "Private"]
        for f in filters:
            btn_text = f"{f} ({counts[f]})"
            is_active = self.active_filter == f
            btn = StyledButton(
                text=btn_text,
                variant="primary_solid" if is_active else "secondary_solid",
                size_hint_x=None,
                width=dp(110),
            )
            # Use default arg capturing for lambda in loop
            btn.bind(on_release=lambda x, f_name=f: self._set_active_filter(f_name))
            self.filter_tabs_container.add_widget(btn)

        self.filter_tabs_container.add_widget(Label(size_hint_x=1))  # Spacer

    def _rebuild_calendar(self):
        """Rebuild the calendar grid with video data."""
        self.calendar_container.clear_widgets()

        filtered_videos = []
        for v in self.videos:
            privacy = v.get("privacyStatus", "private").capitalize()
            if self.active_filter == "All" or privacy == self.active_filter:
                filtered_videos.append(v)

        self.count_label.text = f"{len(filtered_videos)} videos"

        # Build a map of date -> videos
        video_map = {}
        for v in filtered_videos:
            pub = v.get("publishedAt", "")
            if pub:
                try:
                    dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    key = (dt.year, dt.month, dt.day)
                    if key not in video_map:
                        video_map[key] = []
                    video_map[key].append(v)
                except Exception:
                    pass

        # Day name headers
        header = GridLayout(
            cols=7,
            size_hint_y=None,
            height=dp(30),
            spacing=dp(2),
        )
        for day_name in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            lbl = Label(
                text=day_name,
                font_name=theme.FONT_FAMILY,
                font_size="11sp",
                bold=True,
                color=theme.hex_to_rgba(theme.FG_MUTED, 0.7),
                halign="center",
                valign="middle",
                size_hint_y=None,
                height=dp(28),
            )
            lbl.bind(size=lbl.setter("text_size"))
            header.add_widget(lbl)
        self.calendar_container.add_widget(header)

        # Calendar days grid
        cal = calendar.Calendar(firstweekday=0)  # Monday first
        weeks = cal.monthdayscalendar(self.current_year, self.current_month)

        today = datetime.date.today()

        for week in weeks:
            row = GridLayout(
                cols=7,
                size_hint_y=None,
                height=dp(90),
                spacing=dp(2),
            )
            for day in week:
                cell = self._make_day_cell(day, video_map, today)
                row.add_widget(cell)
            self.calendar_container.add_widget(row)

    def _make_day_cell(self, day, video_map, today):
        """Create a single calendar day cell."""
        cell = BoxLayout(
            orientation="vertical",
            padding=dp(4),
            spacing=dp(2),
        )

        is_today = (
            day > 0
            and day == today.day
            and self.current_month == today.month
            and self.current_year == today.year
        )

        # Background
        if day == 0:
            bg_alpha = 0.01
        elif is_today:
            bg_alpha = 0.08
        else:
            bg_alpha = 0.03

        with cell.canvas.before:
            if is_today:
                Color(*theme.hex_to_rgba(theme.ACCENT, 0.15))
            else:
                Color(1, 1, 1, bg_alpha)
            cell._bg = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[6])

        if is_today:
            with cell.canvas.after:
                Color(*theme.hex_to_rgba(theme.ACCENT, 0.4))
                cell._border = Line(
                    rounded_rectangle=(
                        cell.x,
                        cell.y,
                        cell.width,
                        cell.height,
                        6,
                    ),
                    width=1.2,
                )

            def update_with_border(instance, *args):
                instance._bg.pos = instance.pos
                instance._bg.size = instance.size
                instance._border.rounded_rectangle = (
                    instance.x,
                    instance.y,
                    instance.width,
                    instance.height,
                    6,
                )

            cell.bind(pos=update_with_border, size=update_with_border)
        else:

            def update_no_border(instance, *args):
                instance._bg.pos = instance.pos
                instance._bg.size = instance.size

            cell.bind(pos=update_no_border, size=update_no_border)

        if day == 0:
            # Empty cell for padding days
            cell.add_widget(Label())
            return cell

        # Day number
        day_color = (
            theme.hex_to_rgba(theme.FG)
            if not is_today
            else theme.hex_to_rgba(theme.ACCENT)
        )
        day_label = Label(
            text=str(day),
            font_name=theme.FONT_FAMILY,
            font_size="12sp",
            bold=is_today,
            color=day_color,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(16),
        )
        day_label.bind(size=day_label.setter("text_size"))
        cell.add_widget(day_label)

        # Videos for this day
        key = (self.current_year, self.current_month, day)
        day_videos = video_map.get(key, [])

        if day_videos:
            for v in day_videos[:2]:  # Max 2 visible
                title = v.get("title", "")
                if len(title) > 18:
                    title = title[:16] + ".."

                privacy = v.get("privacyStatus", "private")
                if privacy == "public":
                    dot_color = theme.hex_to_rgba(theme.SUCCESS)
                elif privacy == "unlisted":
                    dot_color = theme.hex_to_rgba(theme.ACCENT)
                else:
                    dot_color = theme.hex_to_rgba(theme.FG_MUTED, 0.6)

                vid_label = Label(
                    text=title,
                    font_name=theme.FONT_FAMILY,
                    font_size="9sp",
                    color=dot_color,
                    halign="left",
                    valign="top",
                    size_hint_y=None,
                    height=dp(14),
                )
                vid_label.bind(size=vid_label.setter("text_size"))
                cell.add_widget(vid_label)

            if len(day_videos) > 2:
                more = Label(
                    text=f"+{len(day_videos) - 2} more",
                    font_name=theme.FONT_FAMILY,
                    font_size="8sp",
                    color=theme.hex_to_rgba(theme.FG_MUTED, 0.5),
                    halign="left",
                    valign="top",
                    size_hint_y=None,
                    height=dp(12),
                )
                more.bind(size=more.setter("text_size"))
                cell.add_widget(more)
        else:
            # Empty spacer
            cell.add_widget(Label())

        return cell
