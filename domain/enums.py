from enum import Enum


class CommandType(Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    DELETE = "DELETE"
    UPDATE = "UPDATE"
    UNKNOWN = "UNKNOWN"


class ConnectionStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    ERROR = "Error"
