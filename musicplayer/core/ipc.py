"""
IPC (Inter-Process Communication) Module

Handles communication between the main player process (server)
and the library subprocess (client) using QLocalSocket.

- IPCServer: Runs in the main player, listens for one client.
- IPCClient: Runs in the library, connects to the server.

Protocol:
- JSON-based messages separated by newline character ('\\n').
- Each message is a dict: {"type": "command_name", "payload": ...}
"""
import json
import sys
from PySide6.QtCore import (QObject, Signal, QTimer, QByteArray,
                            QDataStream, QIODevice)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Server name can be customized to avoid conflicts
SERVER_NAME = "SonicFlamePlayerIPC_v2"


class IPCServer(QObject):
    """
    IPC Server for the main player process. Listens for a single client (library).
    """
    client_connected = Signal()
    client_disconnected = Signal()
    
    # Signals for commands from client
    play_track_requested = Signal(str)
    artist_play_requested = Signal(str)
    library_closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._client_socket = None
        self._server.newConnection.connect(self._on_new_connection)

    def start(self):
        """Starts listening for connections."""
        # Ensure server is clean before starting
        QLocalServer.removeServer(SERVER_NAME)
        if not self._server.listen(SERVER_NAME):
            print(f"IPCServer: Failed to start listening on {SERVER_NAME}", file=sys.stderr)
            return False
        print(f"IPCServer: Listening on {SERVER_NAME}", file=sys.stderr)
        return True

    def stop(self):
        """Stops the server."""
        if self._client_socket:
            self._client_socket.disconnectFromServer()
        self._server.close()
        print("IPCServer: Stopped.", file=sys.stderr)

    def is_client_connected(self) -> bool:
        """Check if a client is currently connected."""
        return self._client_socket is not None and self._client_socket.isOpen()

    def _on_new_connection(self):
        """Handles a new client connection."""
        if self.is_client_connected():
            # Allow only one client, reject others
            new_socket = self._server.nextPendingConnection()
            if new_socket:
                new_socket.disconnectFromServer()
            return

        self._client_socket = self._server.nextPendingConnection()
        if not self._client_socket:
            return

        self._client_socket.readyRead.connect(self._on_ready_read)
        self._client_socket.disconnected.connect(self._on_client_disconnected)
        self.client_connected.emit()
        print("IPCServer: Client connected.", file=sys.stderr)

    def _on_client_disconnected(self):
        """Handles client disconnection."""
        print("IPCServer: Client disconnected.", file=sys.stderr)
        if self._client_socket:
            self._client_socket.deleteLater()
            self._client_socket = None
        self.client_disconnected.emit()

    def _on_ready_read(self):
        """Reads and processes messages from the client."""
        if not self.is_client_connected():
            return
            
        buffer = self._client_socket.readAll().data()
        for chunk in buffer.split(b'\\n'):
            if not chunk:
                continue
            try:
                message = json.loads(chunk.decode('utf-8'))
                self._process_command(message)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"IPCServer: Error decoding message: {e}", file=sys.stderr)

    def _process_command(self, command: dict):
        """Processes a single command dictionary."""
        cmd_type = command.get("type")
        payload = command.get("payload")

        if cmd_type == "play":
            if isinstance(payload, dict) and "filepath" in payload:
                self.play_track_requested.emit(payload["filepath"])
        elif cmd_type == "play_artist":
            if isinstance(payload, dict) and "artist" in payload:
                self.artist_play_requested.emit(payload["artist"])
        elif cmd_type == "close":
            self.library_closed.emit()

    def _send_command(self, command: dict):
        """Sends a JSON command to the connected client."""
        if not self.is_client_connected():
            # print("IPCServer: Cannot send command, no client connected.", file=sys.stderr)
            return
        
        try:
            payload = json.dumps(command).encode("utf-8") + b'\\n'
            self._client_socket.write(payload)
            self._client_socket.flush()
        except Exception as e:
            print(f"IPCServer: Failed to send command: {e}", file=sys.stderr)
            
    # --- Public methods to send commands to client ---
    def send_refresh(self):
        self._send_command({"type": "refresh"})
        
    def send_close(self):
        self._send_command({"type": "close"})
        
    def send_show(self):
        self._send_command({"type": "show"})
        
    def send_accent_color(self, color: str):
        self._send_command({"type": "accent_color", "payload": {"color": color}})


class IPCClient(QObject):
    """
    IPC Client for the library subprocess. Connects to the main player.
    """
    connected = Signal()
    disconnected = Signal()
    
    # Signals for commands from server
    refresh_requested = Signal()
    close_requested = Signal()
    show_requested = Signal()
    accent_color_changed = Signal(str)

    def __init__(self, server_name: str, parent=None):
        super().__init__(parent)
        self._server_name = server_name
        self._socket = QLocalSocket(self)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(500)  # Retry every 500ms
        self._reconnect_timer.timeout.connect(self.connect_to_server)
        
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        
    def start(self):
        """Start trying to connect to the server."""
        print(f"IPCClient: Attempting to connect to {self._server_name}", file=sys.stderr)
        self.connect_to_server()

    def stop(self):
        """Stops the client and disconnects."""
        self._reconnect_timer.stop()
        self._socket.disconnectFromServer()
        print("IPCClient: Stopped.", file=sys.stderr)
        
    def connect_to_server(self):
        """Tries to connect to the server."""
        if self._socket.state() == QLocalSocket.ConnectedState:
            return
        self._socket.connectToServer(self._server_name)

    def _on_connected(self):
        """Handles successful connection."""
        self._reconnect_timer.stop()
        self.connected.emit()
        print("IPCClient: Connected to server.", file=sys.stderr)
        
    def _on_disconnected(self):
        """Handles disconnection and schedules a reconnect."""
        self.disconnected.emit()
        print("IPCClient: Disconnected from server. Retrying...", file=sys.stderr)
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def _on_ready_read(self):
        """Reads and processes messages from the server."""
        buffer = self._socket.readAll().data()
        for chunk in buffer.split(b'\\n'):
            if not chunk:
                continue
            try:
                message = json.loads(chunk.decode('utf-8'))
                self._process_command(message)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"IPCClient: Error decoding message: {e}", file=sys.stderr)

    def _process_command(self, command: dict):
        """Processes a single command from the server."""
        cmd_type = command.get("type")
        payload = command.get("payload")
        if cmd_type == "refresh":
            self.refresh_requested.emit()
        elif cmd_type == "close":
            self.close_requested.emit()
        elif cmd_type == "show":
            self.show_requested.emit()
        elif cmd_type == "accent_color":
            if isinstance(payload, dict) and "color" in payload:
                self.accent_color_changed.emit(payload["color"])

    def _send_command(self, command: dict):
        """Sends a JSON command to the server."""
        if self._socket.state() != QLocalSocket.ConnectedState:
            print("IPCClient: Not connected, cannot send command.", file=sys.stderr)
            return
            
        try:
            payload = json.dumps(command).encode("utf-8") + b'\\n'
            self._socket.write(payload)
            self._socket.flush()
        except Exception as e:
            print(f"IPCClient: Failed to send command: {e}", file=sys.stderr)

    # --- Public methods to send commands to server ---
    def send_play_track(self, filepath: str):
        self._send_command({"type": "play", "payload": {"filepath": filepath}})

    def send_play_artist(self, artist_name: str):
        self._send_command({"type": "play_artist", "payload": {"artist": artist_name}})

    def send_library_closed(self):
        self._send_command({"type": "close"})

