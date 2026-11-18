"""Application entry point for the Linux and Windows desktop build."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import re
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QIODevice,
    QObject,
    QTimer,
    Signal,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, __version__
from .config import ConfigStore, state_home
from .controller import Controller
from .discord import DiscordClient, DiscordError
from .icons import app_icon
from .media import create_monitor, players_name
from .ui.theme import current_palette

log = logging.getLogger(__name__)


def configure_logging(debug: bool) -> Path:
    log_dir = state_home() / "whatisplaying"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "whatisplaying.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(console)
    return log_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whatisplaying",
        description="Share the track you are listening to as a Discord custom status.",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="start hidden in the system tray when a tray is available",
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="disable the system tray icon",
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument(
        "--list-players",
        action="store_true",
        help="list detected media players and exit",
    )
    parser.add_argument(
        "--send-test",
        action="store_true",
        help="send a test custom status using the saved token and exit",
    )
    parser.add_argument(
        "--clear-status",
        action="store_true",
        help="clear the Discord custom status using the saved token and exit",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _cli(args: argparse.Namespace) -> int | None:
    if not (args.list_players or args.send_test or args.clear_status):
        return None

    if args.list_players:
        app = QCoreApplication([sys.argv[0]])  # noqa: F841 - Qt D-Bus needs an application
        monitor = create_monitor()
        wait_until_ready = getattr(monitor, "wait_until_ready", None)
        if callable(wait_until_ready):
            wait_until_ready(5.0)
        players = monitor.refresh()
        if not players:
            print(f"No {players_name()} detected.")
            if monitor.error:
                print(monitor.error)
            return 1
        for player in players:
            print(f"{player.identity}  [{player.key}]  {player.display_status}")
            if player.title:
                artist = f" — {player.artist}" if player.artist else ""
                print(f"    {player.title}{artist}")
        return 0

    store = ConfigStore()
    config = store.load()
    token = config.token.strip()
    if not token:
        print("No Discord token saved. Run whatisplaying and add one first.")
        return 1

    try:
        client = DiscordClient(token)
        if args.send_test:
            client.update("WhatIsPlaying test (｡･ω･｡)")
            print("Test status sent to Discord.")
        else:
            client.clear()
            print("Discord custom status cleared.")
        return 0
    except DiscordError as exc:
        print(f"Discord request failed: {exc}", file=sys.stderr)
        return 1


def _socket_name() -> str:
    if hasattr(os, "getuid"):
        return f"whatisplaying-{os.getuid()}"
    # Windows has no getuid(); the username keeps separate sessions apart.
    user = re.sub(r"[^A-Za-z0-9_.-]", "_", getpass.getuser() or "user")
    return f"whatisplaying-{user}"


def _set_windows_app_id() -> None:
    """Give the process a stable identity for the taskbar and tray."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception as exc:  # noqa: BLE001 - cosmetic only
        log.debug("Could not set the Windows AppUserModelID: %s", exc)


class SingleInstance(QObject):
    show_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.server: QLocalServer | None = None
        self._name = _socket_name()

    def notify_existing(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._name, QIODevice.OpenModeFlag.WriteOnly)
        if not socket.waitForConnected(300):
            return False
        socket.write(b"show\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        QLocalServer.removeServer(self._name)
        server = QLocalServer(self)
        try:
            server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        except AttributeError:
            pass
        if not server.listen(self._name):
            log.warning("Could not start single-instance server: %s", server.errorString())
            return False
        server.newConnection.connect(self._on_connection)
        self.server = server
        return True

    def _on_connection(self) -> None:
        if self.server is None:
            return
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            if connection is None:
                continue
            connection.readyRead.connect(
                lambda conn=connection: self._read_connection(conn)
            )
            connection.disconnected.connect(connection.deleteLater)
            if connection.bytesAvailable():
                self._read_connection(connection)

    def _read_connection(self, connection: QLocalSocket) -> None:
        data = bytes(connection.readAll())
        if b"show" in data:
            self.show_requested.emit()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = _parser().parse_args(argv)

    log_path = configure_logging(args.debug)
    log.info("%s %s starting", APP_NAME, __version__)

    cli_result = _cli(args)
    if cli_result is not None:
        return cli_result

    _set_windows_app_id()
    app = QApplication([sys.argv[0]])
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())

    instance = SingleInstance(app)
    if instance.notify_existing():
        log.info("An existing instance is already running; asking it to show.")
        return 0
    instance.listen()

    palette = current_palette(app)
    store = ConfigStore()
    config = store.load()
    controller = Controller(store, config)
    log.info("Config file: %s", store.path)
    log.info("Log file: %s", log_path)

    from .ui.main_window import MainWindow

    window = MainWindow(controller, palette, tray_enabled=not args.no_tray)
    instance.show_requested.connect(window.show_window)
    app.aboutToQuit.connect(controller.shutdown)

    controller.start()
    if args.minimized and window.tray_available:
        window.hide()
    else:
        window.show()

    quit_signal = lambda *_args: app.quit()  # noqa: E731
    signal.signal(signal.SIGINT, quit_signal)
    signal.signal(signal.SIGTERM, quit_signal)

    # Give Python a chance to run signal handlers while Qt owns the event loop.
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(500)

    quit_after = os.environ.get("WHATISPLAYING_QUIT_AFTER_MS", "").strip()
    if quit_after.isdigit() and int(quit_after) > 0:
        QTimer.singleShot(int(quit_after), app.quit)

    exit_code = app.exec()

    # PySide6 can crash at interpreter shutdown when a top-level widget is
    # destroyed by Python after QApplication is already gone: the binding
    # manager then visits a child wrapper whose C++ object no longer exists.
    # Delete the window explicitly while the application is still alive.
    window.hide()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    log.info("%s stopped", APP_NAME)
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
