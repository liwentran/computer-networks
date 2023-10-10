from cougarnet.util import \
        ip_str_to_binary, ip_binary_to_str
import struct
from headers import IPv4Header, UDPHeader, TCPHeader, \
        IP_HEADER_LEN, UDP_HEADER_LEN, TCP_HEADER_LEN, \
        TCPIP_HEADER_LEN, UDPIP_HEADER_LEN
from host import Host
from mysocket import UDPSocket, TCPSocketBase

class TransportHost(Host):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.socket_mapping_udp = {}
        self.socket_mapping_tcp = {}

    def handle_tcp(self, pkt: bytes) -> None:
        """Called by handle_ip() when packet is dtermined to be a TCP packet."""
        # look for open TCP socket corresponding with the 4-tuple of the incoming packet
        src_address = ip_binary_to_str(pkt[12:16])
        dst_address = ip_binary_to_str(pkt[16:20])
        sport, = struct.unpack('!H', pkt[IP_HEADER_LEN:IP_HEADER_LEN+2])
        dport, = struct.unpack('!H', pkt[IP_HEADER_LEN+2:IP_HEADER_LEN+4])

        if socket := self.socket_mapping_tcp.get((dst_address, dport, src_address, sport)):
            # if 4-tuple mapping is found, call handle_packet() on socket
            socket.handle_packet(pkt)
        elif listener_socket := self.socket_mapping_tcp.get((dst_address, dport, None, None)):
            # look for maping with the local address+port, and call handle_packet() on TCPListenerSocket
            listener_socket.handle_packet(pkt)
        else:
            self.no_socket_tcp(pkt)

    def handle_udp(self, pkt: bytes) -> None:
        """
        Look for an open UDP socket corresponding to its destination address 
        and destination port of the incoming packet, and handle that packet if
        it exists.
        """
        # find destination address and destination port
        dst_address = ip_binary_to_str(pkt[16:20])
        dport, = struct.unpack('!H', pkt[IP_HEADER_LEN+2:IP_HEADER_LEN+4])
                
        if socket := self.socket_mapping_udp.get((dst_address, dport)):
            # open UDP socket corresponding to the dst address and port of the incoming packet exists
            socket.handle_packet(pkt)
        else:
            # no mapping found
            self.no_socket_udp(pkt)


                

    def install_socket_udp(self, local_addr: str, local_port: int,
            sock: UDPSocket) -> None:
        self.socket_mapping_udp[(local_addr, local_port)] = sock

    def install_listener_tcp(self, local_addr: str, local_port: int,
            sock: TCPSocketBase) -> None:
        self.socket_mapping_tcp[(local_addr, local_port, None, None)] = sock

    def install_socket_tcp(self, local_addr: str, local_port: int,
            remote_addr: str, remote_port: int, sock: TCPSocketBase) -> None:
        self.socket_mapping_tcp[(local_addr, local_port, \
                remote_addr, remote_port)] = sock

    def no_socket_udp(self, pkt: bytes) -> None:
        pass

    def no_socket_tcp(self, pkt: bytes) -> None:
        pass
