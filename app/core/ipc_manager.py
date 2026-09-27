"""
Single-Instance Application IPC Manager
Enables desktop-grade tab remoting via QLocalServer / QLocalSocket (Named Pipes on Windows):
- When a user opens files from Windows Explorer or the terminal, they open in the already-running
  instance as a new tab instead of launching multiple heavy processes.
- Brings the primary window to the foreground.
- Bypassed in headless CI/CD mode or when --new-window is explicitly specified.
"""

import os
import sys
import json
import getpass
from typing import List, Callable, Optional
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtCore import QObject, Signal


def get_server_name() -> str:
    """Returns a unique server name per user."""
    user = getpass.getuser().replace(" ", "_")
    return f"diff_and_compare_tool_IPC_{user}"


class SingleInstanceManager(QObject):
    """Manages single-instance application lifecycle and IPC messaging."""

    messageReceived = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server: Optional[QLocalServer] = None
        self.server_name = get_server_name()

    @classmethod
    def try_send_to_existing_instance(cls, args: List[str]) -> bool:
        """
        Attempts to connect to an existing running instance and dispatch command line arguments.
        Returns True if successfully handled by an existing instance, False otherwise.
        """
        # Do not route to existing instance if --new-window or headless flags are present
        if "--new-window" in args or "--headless" in args or "--report-html" in args or "--exit-code" in args:
            return False

        server_name = get_server_name()
        socket = QLocalSocket()
        socket.connectToServer(server_name)

        if socket.waitForConnected(400):
            payload = json.dumps({
                "args": args,
                "cwd": os.getcwd()
            }).encode("utf-8")

            socket.write(payload)
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return True

        return False

    def start_server(self, on_message_callback: Callable[[dict], None]) -> bool:
        """Starts the local IPC server to listen for commands from subsequent instances."""
        self.messageReceived.connect(on_message_callback)

        self.server = QLocalServer(self)
        # Clean up any stale pipe from previous ungraceful exits
        QLocalServer.removeServer(self.server_name)

        if self.server.listen(self.server_name):
            self.server.newConnection.connect(self._on_new_connection)
            return True
        return False

    def _on_new_connection(self):
        socket = self.server.nextPendingConnection()
        if not socket:
            return

        def handle_read():
            data = socket.readAll().data()
            if data:
                try:
                    payload = json.loads(data.decode("utf-8"))
                    self.messageReceived.emit(payload)
                except Exception:
                    pass
            socket.disconnectFromServer()

        socket.readyRead.connect(handle_read)

    def cleanup(self):
        if self.server:
            self.server.close()
            QLocalServer.removeServer(self.server_name)
