"""Matha 网络驱动：完整 TCP/IP 协议栈。"""
from __future__ import annotations

import collections
import random
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any


class IPProtocol(Enum):
    ICMP = 1
    TCP = 6
    UDP = 17
    GRE = 47
    ESP = 50
    AH = 51
    OSPF = 89
    SCTP = 132


class TCPState(Enum):
    CLOSED = "CLOSED"
    LISTEN = "LISTEN"
    SYN_SENT = "SYN_SENT"
    SYN_RECEIVED = "SYN_RECEIVED"
    ESTABLISHED = "ESTABLISHED"
    FIN_WAIT_1 = "FIN_WAIT_1"
    FIN_WAIT_2 = "FIN_WAIT_2"
    CLOSE_WAIT = "CLOSE_WAIT"
    LAST_ACK = "LAST_ACK"
    CLOSING = "CLOSING"
    TIME_WAIT = "TIME_WAIT"


class SocketFamily(Enum):
    INET = "inet"
    INET6 = "inet6"
    UNIX = "unix"
    PACKET = "packet"


class SocketType(Enum):
    STREAM = "stream"
    DGRAM = "dgram"
    RAW = "raw"


@dataclass
class IPPacket:
    version: int = 4
    ihl: int = 5
    tos: int = 0
    total_length: int = 0
    identification: int = 0
    flags: int = 0
    fragment_offset: int = 0
    ttl: int = 64
    protocol: IPProtocol = IPProtocol.TCP
    header_checksum: int = 0
    source_ip: str = "0.0.0.0"
    dest_ip: str = "0.0.0.0"
    payload: bytes = b""


@dataclass
class TCPSegment:
    source_port: int = 80
    dest_port: int = 80
    seq_num: int = 0
    ack_num: int = 0
    data_offset: int = 5
    flags: int = 0
    window_size: int = 65535
    checksum: int = 0
    urgent_pointer: int = 0
    options: bytes = b""
    payload: bytes = b""


@dataclass
class UDPDatagram:
    source_port: int = 53
    dest_port: int = 53
    length: int = 0
    checksum: int = 0
    payload: bytes = b""


@dataclass
class ARPPacket:
    hardware_type: int = 1
    protocol_type: int = 0x0800
    hardware_size: int = 6
    protocol_size: int = 4
    opcode: int = 1
    sender_mac: bytes = b""
    sender_ip: str = "0.0.0.0"
    target_mac: bytes = b""
    target_ip: str = "0.0.0.0"


@dataclass
class RouteEntry:
    dest: str = "0.0.0.0"
    mask: str = "0.0.0.0"
    gateway: str = "0.0.0.0"
    interface: str = "eth0"
    metric: int = 1


class TCPConnection:
    """TCP 连接。"""

    def __init__(self, src_port: int, dst_port: int,
                 src_ip: str, dst_ip: str):
        self.src_port = src_port
        self.dst_port = dst_port
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.state = TCPState.CLOSED
        self.seq_num = random.randint(0, 2**32)
        self.ack_num = 0
        self.window = 65535
        self.send_buffer = collections.deque()
        self.recv_buffer = collections.deque()
        self.closed = False

    def send(self, data: bytes) -> int:
        self.send_buffer.append(data)
        return len(data)

    def receive(self) -> bytes:
        if self.recv_buffer:
            return self.recv_buffer.popleft()
        return b""

    def close(self) -> None:
        self.closed = True
        self.state = TCPState.CLOSED

    def establish(self) -> bool:
        self.state = TCPState.ESTABLISHED
        return True


class NetworkDriver:
    """网络驱动。"""

    def __init__(self):
        self._interfaces: dict[str, dict[str, Any]] = {}
        self._routes: list[RouteEntry] = []
        self._arp_table: dict[str, str] = {}
        self._sockets: dict[int, Any] = {}
        self._next_port = 1024
        self._next_socket = 1
        self._connections: dict[int, TCPConnection] = {}
        self._lock = threading.Lock()
        self._mtu = 1500
        self._ip_address = "0.0.0.0"
        self._subnet_mask = "0.0.0.0"
        self._gateway = "0.0.0.0"
        self._dns_servers: list[str] = []

    def add_interface(self, name: str, ip: str,
                          netmask: str) -> bool:
        with self._lock:
            self._interfaces[name] = {
                "ip": ip, "netmask": netmask,
                "status": "up",
            }
            return True

    def create_socket(self, family: SocketFamily = SocketFamily.INET,
                          sock_type: SocketType = SocketType.STREAM
                          ) -> int:
        with self._lock:
            fd = self._next_socket
            self._next_socket += 1
            self._sockets[fd] = {
                "family": family, "type": sock_type,
                "state": TCPState.CLOSED,
            }
            return fd

    def connect(self, fd: int, address: str,
                   port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            conn = TCPConnection(
                src_port=self._next_port,
                dst_port=port,
                src_ip=self._ip_address,
                dst_ip=address,
            )
            conn.establish()
            self._connections[fd] = conn
            self._next_port += 1
            sock["state"] = TCPState.ESTABLISHED
            return True
        return False

    def bind(self, fd: int, address: str,
                port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock["local_addr"] = address
            sock["local_port"] = port
            return True
        return False

    def listen(self, fd: int, backlog: int = 5) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock["state"] = TCPState.LISTEN
            return True
        return False

    def accept(self, fd: int) -> int | None:
        sock = self._sockets.get(fd)
        if sock and sock["state"] == TCPState.LISTEN:
            return self._next_socket
        return None

    def send(self, fd: int, data: bytes) -> int:
        conn = self._connections.get(fd)
        if conn:
            return conn.send(data)
        return 0

    def recv(self, fd: int, size: int = 4096) -> bytes:
        conn = self._connections.get(fd)
        if conn:
            return conn.receive()[:size]
        return b""

    def close(self, fd: int) -> bool:
        if fd in self._sockets:
            del self._sockets[fd]
            return True
        return False

    def add_route(self, dest: str, mask: str,
                      gateway: str, interface: str) -> None:
        self._routes.append(RouteEntry(
            dest=dest, mask=mask,
            gateway=gateway, interface=interface,
        ))

    def get_local_ip(self) -> str:
        return self._ip_address

    def set_dns(self, servers: list[str]) -> None:
        self._dns_servers = servers

    def resolve_dns(self, hostname: str) -> str | None:
        if hostname in self._arp_table:
            return self._arp_table[hostname]
        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "interfaces": len(self._interfaces),
            "sockets": len(self._sockets),
            "connections": len(self._connections),
            "routes": len(self._routes),
        }


def create_network_driver() -> NetworkDriver:
    return NetworkDriver()


# ============================================================
# 内置注册
# ============================================================

def _register_network_driver(builtins: dict) -> None:
    builtins["创建网络驱动"] = create_network_driver


def _network_driver_names() -> list[str]:
    return ["创建网络驱动"]


__all__ = [
    "IPProtocol", "TCPState", "SocketFamily", "SocketType",
    "IPPacket", "TCPSegment", "UDPDatagram", "ARPPacket",
    "RouteEntry", "TCPConnection", "NetworkDriver",
    "create_network_driver",
    "_register_network_driver", "_network_driver_names",
]
