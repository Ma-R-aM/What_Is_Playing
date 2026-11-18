"""Main window for the WhatIsPlaying desktop app."""

from __future__ import annotations

import html
import logging
import time

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QCloseEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..autostart import is_enabled as autostart_is_enabled
from ..autostart import set_enabled as autostart_set_enabled
from ..config import state_home
from ..controller import AppState, Controller
from ..icons import app_icon, render_pixmap
from ..media import empty_list_hint, platform_badge, support_hint
from ..parser import clean_artist, clean_title
from .theme import Palette, current_palette, stylesheet
from .widgets import PlayerRow, StatusDot, ToggleSwitch

log = logging.getLogger(__name__)


def _label(
    text: str = "",
    object_name: str | None = None,
    *,
    wrap: bool = False,
) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(wrap)
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _set_label_kind(label: QLabel, kind: str) -> None:
    if label.objectName() == kind:
        return
    label.setObjectName(kind)
    _repolish(label)


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: Controller,
        palette: Palette,
        *,
        tray_enabled: bool = True,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self._palette = palette
        self._state: AppState | None = None
        self._player_signature: tuple | None = None
        self._quitting = False
        self._tray_notice_shown = False
        self._tray_available = False

        self.setWindowTitle("WhatIsPlaying")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(540, 620)
        self.resize(650, 850)

        self._build_ui()
        self.setStyleSheet(stylesheet(palette))
        self._setup_tray(tray_enabled)
        self.tray_check.blockSignals(True)
        self.tray_check.setChecked(self.config.close_to_tray and self._tray_available)
        self.tray_check.blockSignals(False)
        self.tray_check.setEnabled(self._tray_available)
        self._setup_shortcuts()

        controller.state_changed.connect(self._on_state)
        controller.activity.connect(self._append_activity)

        try:
            QApplication.instance().styleHints().colorSchemeChanged.connect(
                self._on_scheme_changed
            )
        except AttributeError:
            pass

        self._append_activity("info", "Ready.")

    # ------------------------------------------------------------------- UI
    @property
    def tray_available(self) -> bool:
        return self._tray_available

    def _build_ui(self) -> None:
        p = self._palette
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("Scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        column = QVBoxLayout(content)
        column.setContentsMargins(22, 22, 22, 26)
        column.setSpacing(14)
        column.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)

        # ---------------------------------------------------------- intro
        intro = QFrame()
        intro.setObjectName("IntroCard")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(20, 18, 20, 18)
        intro_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(14)
        icon = QLabel()
        icon.setPixmap(render_pixmap(58))
        icon.setFixedSize(58, 58)
        icon.setScaledContents(True)
        top.addWidget(icon)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = _label(APP_NAME, "IntroTitle")
        subtitle = _label(
            "Share what you are listening to as a Discord custom status.",
            "IntroBody",
            wrap=True,
        )
        titles.addWidget(title)
        titles.addWidget(subtitle)
        top.addLayout(titles, 1)

        badge = _label(platform_badge(), "Badge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        intro_layout.addLayout(top)
        column.addWidget(intro)

        # --------------------------------------------------------- status
        status_card = self._card()
        status_layout = status_card.layout()
        row = QHBoxLayout()
        row.setSpacing(12)
        labels = QVBoxLayout()
        labels.setSpacing(2)
        labels.addWidget(_label("Send to Discord", "CardTitle"))
        self.switch_desc = _label(
            "Now playing will be shared as your custom status.", "Hint", wrap=True
        )
        labels.addWidget(self.switch_desc)
        row.addLayout(labels, 1)

        self.enabled_switch = ToggleSwitch(p)
        self.enabled_switch.setChecked(self.config.enabled)
        self.enabled_switch.setAccessibleName("Send to Discord")
        self.enabled_switch.toggled.connect(self.controller.set_enabled)
        row.addWidget(self.enabled_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        status_layout.addLayout(row)
        status_layout.addWidget(_divider())

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_dot = StatusDot(p.muted)
        status_row.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignTop)
        status_labels = QVBoxLayout()
        status_labels.setSpacing(1)
        self.status_summary = _label("Ready", "CardTitle", wrap=True)
        self.status_detail = _label(
            "Start a music player to share what is playing.", "Muted", wrap=True
        )
        status_labels.addWidget(self.status_summary)
        status_labels.addWidget(self.status_detail)
        status_row.addLayout(status_labels, 1)
        status_layout.addLayout(status_row)

        self.status_error = _label("", "Error", wrap=True)
        self.status_error.hide()
        status_layout.addWidget(self.status_error)
        column.addWidget(status_card)

        # ---------------------------------------------------- now playing
        playing_card = self._card()
        playing_layout = playing_card.layout()
        header = QHBoxLayout()
        header.addWidget(_label("Now playing", "CardTitle"), 1)
        self.track_pill = _label("Idle", "PillMuted")
        self.track_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.track_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        playing_layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        art = QFrame()
        art.setFixedSize(66, 66)
        art.setStyleSheet(
            f"background: {p.field}; border: 1px solid {p.border}; border-radius: 16px;"
        )
        art_layout = QVBoxLayout(art)
        art_layout.setContentsMargins(0, 0, 0, 0)
        note = QLabel("♪")
        note.setObjectName("Note")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art_layout.addWidget(note)
        self._art = art
        body.addWidget(art, 0, Qt.AlignmentFlag.AlignTop)

        track_labels = QVBoxLayout()
        track_labels.setSpacing(2)
        self.track_title = _label("Nothing playing", "TrackTitle", wrap=True)
        self.track_artist = _label(
            support_hint(), "TrackArtist", wrap=True
        )
        self.track_source = _label("Waiting for a player…", "TrackSource", wrap=True)
        track_labels.addWidget(self.track_title)
        track_labels.addWidget(self.track_artist)
        track_labels.addWidget(self.track_source)
        body.addLayout(track_labels, 1)
        playing_layout.addLayout(body)

        self.track_preview = _label("", "Hint", wrap=True)
        self.track_preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.track_preview.hide()
        playing_layout.addWidget(self.track_preview)
        column.addWidget(playing_card)

        # -------------------------------------------------------- players
        players_card = self._card()
        players_layout = players_card.layout()
        header = QHBoxLayout()
        header.addWidget(_label("Music players", "CardTitle"), 1)
        self.players_count = _label("", "Muted")
        header.addWidget(self.players_count, 0, Qt.AlignmentFlag.AlignVCenter)
        players_layout.addLayout(header)
        players_layout.addWidget(
            _label(
                "Only checked players can update your Discord status.",
                "Hint",
                wrap=True,
            )
        )

        self.players_box = QVBoxLayout()
        self.players_box.setSpacing(7)
        players_layout.addLayout(self.players_box)

        self.players_hint = _label("", "Muted", wrap=True)
        players_layout.addWidget(self.players_hint)

        self.monitor_error = _label("", "Error", wrap=True)
        self.monitor_error.hide()
        players_layout.addWidget(self.monitor_error)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.controller.refresh_players)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        select_all = QPushButton("Select all")
        select_all.setObjectName("Flat")
        select_all.clicked.connect(self._select_all_players)
        buttons.addWidget(select_all)
        clear = QPushButton("Clear")
        clear.setObjectName("Flat")
        clear.clicked.connect(lambda: self.controller.set_selected_players(set()))
        buttons.addWidget(clear)
        players_layout.addLayout(buttons)
        column.addWidget(players_card)

        # ---------------------------------------------------------- token
        token_card = self._card()
        token_layout = token_card.layout()
        token_layout.addWidget(_label("Discord token", "CardTitle"))
        token_layout.addWidget(
            _label(
                "Used to update your own Discord custom status. It is stored only "
                "on this computer, readable by your user account.",
                "Hint",
                wrap=True,
            )
        )

        token_row = QHBoxLayout()
        token_row.setSpacing(7)
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Paste your Discord user token")
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setText(self.config.token)
        self.token_edit.setAccessibleName("Discord token")
        self.token_edit.textChanged.connect(self._update_token_hint)
        token_row.addWidget(self.token_edit, 1)

        self.token_visibility = QToolButton()
        self.token_visibility.setText("Show")
        self.token_visibility.setAccessibleName("Show Discord token")
        self.token_visibility.clicked.connect(self._toggle_token_visibility)
        token_row.addWidget(self.token_visibility)

        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_token)
        token_row.addWidget(save)
        token_layout.addLayout(token_row)

        self.token_hint = _label("", "Hint", wrap=True)
        token_layout.addWidget(self.token_hint)

        token_buttons = QHBoxLayout()
        token_buttons.setSpacing(4)
        test = QPushButton("Send test")
        test.clicked.connect(self._send_test)
        token_buttons.addWidget(test)
        clear_status = QPushButton("Clear status && stop")
        clear_status.setObjectName("Flat")
        clear_status.clicked.connect(self.controller.clear_status)
        token_buttons.addWidget(clear_status)
        token_buttons.addStretch(1)
        token_layout.addLayout(token_buttons)

        token_layout.addWidget(
            _label(
                "The app sends PATCH requests to "
                "discord.com/api/v9/users/@me/settings. Using a user token with "
                "third-party automation may violate Discord's Terms of Service — "
                "use at your own risk.",
                "Hint",
                wrap=True,
            )
        )
        column.addWidget(token_card)

        # ---------------------------------------------------- preferences
        prefs_card = self._card()
        prefs_layout = prefs_card.layout()
        prefs_layout.addWidget(_label("Preferences", "CardTitle"))

        self.autostart_check = QCheckBox("Start automatically when I log in")
        self.autostart_check.setChecked(autostart_is_enabled())
        self.autostart_check.toggled.connect(self._toggle_autostart)
        prefs_layout.addWidget(self.autostart_check)

        self.tray_check = QCheckBox("Keep running in the tray when the window is closed")
        self.tray_check.setChecked(
            self.config.close_to_tray and self._tray_availability()
        )
        self.tray_check.toggled.connect(self.controller.set_close_to_tray)
        if not self._tray_availability():
            self.tray_check.setEnabled(False)
            self.tray_check.setToolTip(
                "No system tray is available in this desktop session."
            )
        prefs_layout.addWidget(self.tray_check)

        self.kaomoji_check = QCheckBox("Append a cute kaomoji to the status")
        self.kaomoji_check.setChecked(self.config.append_kaomoji)
        self.kaomoji_check.toggled.connect(self.controller.set_append_kaomoji)
        prefs_layout.addWidget(self.kaomoji_check)
        column.addWidget(prefs_card)

        # ------------------------------------------------------- activity
        log_card = self._card()
        log_layout = log_card.layout()
        log_header = QHBoxLayout()
        log_header.addWidget(_label("Activity", "CardTitle"), 1)
        clear_log = QPushButton("Clear log")
        clear_log.setObjectName("Flat")
        clear_log.clicked.connect(self._clear_log)
        log_header.addWidget(clear_log)
        log_layout.addLayout(log_header)

        self.activity_log = QTextEdit()
        self.activity_log.setObjectName("Log")
        self.activity_log.setReadOnly(True)
        self.activity_log.setMinimumHeight(125)
        self.activity_log.setMaximumHeight(180)
        self.activity_log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.activity_log.document().setMaximumBlockCount(300)
        log_layout.addWidget(self.activity_log)
        column.addWidget(log_card)

        footer = QHBoxLayout()
        footer.addWidget(
            _label(
                f"v{__version__} · local only · no analytics",
                "Hint",
            ),
            1,
        )
        open_logs = QPushButton("Open log folder")
        open_logs.setObjectName("Flat")
        open_logs.clicked.connect(self._open_log_folder)
        footer.addWidget(open_logs)
        column.addLayout(footer)

        self._update_token_hint()
        self._render_players([])

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        return card

    def _setup_shortcuts(self) -> None:
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.quit_app)
        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut.activated.connect(self.controller.refresh_players)
        refresh_shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut_f5.activated.connect(self.controller.refresh_players)

    @staticmethod
    def _tray_availability() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def _setup_tray(self, enabled: bool) -> None:
        self._tray_available = bool(enabled and self._tray_availability())
        if not self._tray_available:
            return

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} — waiting for a player")
        menu = QMenu(self)

        show_action = QAction("Show WhatIsPlaying", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        self.tray_enabled_action = QAction("Send to Discord", self)
        self.tray_enabled_action.setCheckable(True)
        self.tray_enabled_action.setChecked(self.config.enabled)
        self.tray_enabled_action.toggled.connect(self.controller.set_enabled)
        menu.addAction(self.tray_enabled_action)
        menu.addSeparator()

        clear_action = QAction("Clear Discord status", self)
        clear_action.triggered.connect(self.controller.clear_status)
        menu.addAction(clear_action)

        refresh_action = QAction("Refresh players", self)
        refresh_action.triggered.connect(self.controller.refresh_players)
        menu.addAction(refresh_action)
        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_window()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        if self._tray_available:
            self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt name
        if self._quitting:
            event.accept()
            return
        if self._tray_available and self.config.close_to_tray:
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self._tray_notice_shown = True
                self.tray.showMessage(
                    APP_NAME,
                    "Still running in the tray. Use the tray menu to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
            return
        event.ignore()
        self.quit_app()

    # ------------------------------------------------------------- render
    def _on_state(self, state: AppState) -> None:
        self._state = state
        self._render_state(state)

    def _render_state(self, state: AppState) -> None:
        p = self._palette

        self.enabled_switch.blockSignals(True)
        self.enabled_switch.setChecked(state.enabled)
        self.enabled_switch.blockSignals(False)
        if self._tray_available:
            self.tray_enabled_action.blockSignals(True)
            self.tray_enabled_action.setChecked(state.enabled)
            self.tray_enabled_action.blockSignals(False)

        if state.enabled:
            self.switch_desc.setText(
                "Now playing will be shared as your custom status."
            )
        else:
            self.switch_desc.setText(
                "Sending is turned off. Your Discord status is left alone."
            )

        phase = state.phase
        if phase == "disabled":
            dot, summary = p.muted, "Sending is off"
        elif phase == "token-missing":
            dot, summary = p.error, "Discord token needed"
        elif phase == "no-players":
            dot, summary = p.warn, "Waiting for a player"
        elif phase == "not-watching":
            dot, summary = p.warn, "No watched player is active"
        elif phase == "paused":
            dot, summary = p.warn, "Playback paused"
        elif phase == "error":
            dot, summary = p.error, "Discord request failed"
        elif phase == "updating":
            dot, summary = p.primary, "Updating Discord status"
        else:
            dot, summary = p.ok, "Sharing on Discord"

        self.status_dot.set_color(dot)
        self.status_summary.setText(summary)
        self.status_detail.setText(state.message)

        if state.last_error:
            self.status_error.setText(state.last_error)
            self.status_error.show()
        else:
            self.status_error.hide()

        self._render_now_playing(state)
        self._render_players(state.players, state)

        if state.monitor_error:
            self.monitor_error.setText(state.monitor_error)
            self.monitor_error.show()
        else:
            self.monitor_error.hide()

        self._update_token_hint()

        if state.active and state.active.title:
            self.setWindowTitle(
                f"{clean_title(state.active.title) or state.active.title} — {APP_NAME}"
            )
            if self._tray_available:
                self.tray.setToolTip(
                    f"{clean_title(state.active.title) or state.active.title}\n{APP_NAME}"
                )
        else:
            self.setWindowTitle(APP_NAME)
            if self._tray_available:
                self.tray.setToolTip(f"{APP_NAME} — waiting for a player")

    def _render_now_playing(self, state: AppState) -> None:
        active = state.active
        if active is None:
            self.track_title.setText("Nothing playing")
            self.track_artist.setText(support_hint())
            self.track_source.setText("Waiting for a player…")
            self.track_pill.setText("Idle")
            _set_label_kind(self.track_pill, "PillMuted")
            self.track_preview.hide()
            return

        title = clean_title(active.title) or active.title or "Unknown title"
        artist = clean_artist(active.artist) or active.artist or "Unknown artist"
        self.track_title.setText(title)
        self.track_artist.setText(artist)

        source = active.identity
        if active.album:
            source = f"{source} · {active.album}"
        self.track_source.setText(source)

        if active.playback_status == "Playing":
            self.track_pill.setText("Playing")
            _set_label_kind(self.track_pill, "PillOk")
        elif active.playback_status == "Paused":
            self.track_pill.setText("Paused")
            _set_label_kind(self.track_pill, "PillWarn")
        else:
            self.track_pill.setText(active.display_status)
            _set_label_kind(self.track_pill, "PillMuted")

        if state.phase == "playing" and state.status_text:
            self.track_preview.setText(f"Discord: {state.status_text}")
            self.track_preview.show()
        else:
            self.track_preview.hide()

    def _render_players(
        self, players, state: AppState | None = None
    ) -> None:
        selected = (
            None
            if state is None or state.selected_players is None
            else set(state.selected_players)
        )
        signature = tuple(
            (
                p.key,
                p.identity,
                p.bus_name,
                p.playback_status,
                selected is None or p.key in selected,
            )
            for p in players
        )
        if signature != self._player_signature:
            self._player_signature = signature
            while self.players_box.count():
                item = self.players_box.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

            if not players:
                self.players_box.addWidget(
                    _label(empty_list_hint(), "Hint", wrap=True)
                )
            else:
                for player in players:
                    checked = selected is None or player.key in selected
                    row = PlayerRow(
                        identity=player.identity,
                        bus_name=player.bus_name,
                        status=player.playback_status,
                        checked=checked,
                        palette=self._palette,
                        on_toggle=lambda value, key=player.key: self._toggle_player(
                            key, value
                        ),
                    )
                    self.players_box.addWidget(row)

        if selected is None:
            self.players_count.setText("All detected")
            self.players_hint.setText(
                "Watching every detected player, including players started later."
            )
        else:
            self.players_count.setText(f"{len(selected)} selected")
            if not selected:
                self.players_hint.setText(
                    "No players selected — your Discord status will not update."
                )
            else:
                self.players_hint.setText(
                    f"Watching {len(selected)} selected player(s)."
                )

    # ------------------------------------------------------------- actions
    def _toggle_player(self, key: str, checked: bool) -> None:
        players = self._state.players if self._state else ()
        selected = (
            None
            if self._state is None or self._state.selected_players is None
            else set(self._state.selected_players)
        )
        current = {p.key for p in players} if selected is None else set(selected)
        if checked:
            current.add(key)
        else:
            current.discard(key)

        all_keys = {p.key for p in players}
        self.controller.set_selected_players(
            None if current == all_keys else current
        )

    def _select_all_players(self) -> None:
        self.controller.set_selected_players(None)

    def _toggle_token_visibility(self) -> None:
        if self.token_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.token_visibility.setText("Hide")
        else:
            self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.token_visibility.setText("Show")

    def _save_token(self) -> None:
        self.controller.set_token(self.token_edit.text())
        self._update_token_hint()

    def _send_test(self) -> None:
        if self.token_edit.text().strip() != self.config.token:
            self.controller.set_token(self.token_edit.text())
        self.controller.test_status()

    def _update_token_hint(self) -> None:
        if not hasattr(self, "token_hint"):
            return
        saved = self.config.token
        typed = self.token_edit.text().strip()
        if typed and typed != saved:
            self.token_hint.setText("Unsaved changes — press Save to apply.")
            _set_label_kind(self.token_hint, "Error")
        elif saved:
            self.token_hint.setText(
                "Token saved locally. The file is readable only by your user."
            )
            _set_label_kind(self.token_hint, "Hint")
        else:
            self.token_hint.setText("No Discord token saved yet.")
            _set_label_kind(self.token_hint, "Error")

    def _toggle_autostart(self, enabled: bool) -> None:
        try:
            autostart_set_enabled(enabled)
        except OSError as exc:
            log.error("Could not change autostart: %s", exc)
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(not enabled)
            self.autostart_check.blockSignals(False)
            self._append_activity("error", f"Could not change autostart: {exc}")
            return
        log.info("Autostart %s", "enabled" if enabled else "disabled")
        self._append_activity(
            "info",
            "Autostart enabled." if enabled else "Autostart disabled.",
        )

    def _clear_log(self) -> None:
        self.activity_log.clear()
        self._append_activity("info", "Log cleared.")

    def _append_activity(self, level: str, message: str) -> None:
        if not hasattr(self, "activity_log"):
            return
        p = self._palette
        color = {"warning": p.warn, "error": p.error}.get(level, p.muted)
        marker = {"warning": "!", "error": "×"}.get(level, "•")
        stamp = time.strftime("%H:%M:%S")
        self.activity_log.append(
            f'<span style="color:{color}">[{stamp}] {marker} '
            f"{html.escape(message)}</span>"
        )
        bar = self.activity_log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _open_log_folder(self) -> None:
        path = state_home() / "whatisplaying"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._append_activity("error", f"Could not create log folder: {exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_scheme_changed(self, *_args) -> None:
        palette = current_palette(QApplication.instance())
        if palette == self._palette:
            return
        self._palette = palette
        self.setStyleSheet(stylesheet(palette))
        for switch in self.findChildren(ToggleSwitch):
            switch.apply_theme(palette)
        self._art.setStyleSheet(
            f"background: {palette.field}; border: 1px solid {palette.border}; "
            "border-radius: 16px;"
        )
        self._player_signature = None
        if self._state is not None:
            self._render_state(self._state)
