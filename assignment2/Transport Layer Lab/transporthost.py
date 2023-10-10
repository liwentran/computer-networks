from cougarnet.util import \
        ip_str_to_binary, ip_binary_to_str
import struct
from headers import ICMP_HEADER_LEN, IPv4Header, UDPHeader, TCPHeader, ICMPHeader, \
        IP_HEADER_LEN, UDP_HEADER_LEN, TCP_HEADER_LEN, \
        TCPIP_HEADER_LEN, UDPIP_HEADER_LEN
from host import IPPROTO_TCP, Host
from mysocket import IPV4_TTL_DEFAULT, TCP_FLAGS_RST, UDPSocket, TCPSocketBase

IPPROTO_ICMP = 1 # Internet Control Message Protocol

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
        """Return an ICMP Port Unreachable message to the sender"""
        # create a new IPv4 header using the pkt's src and dst
        pkt_ipv4_header = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        ipv4_header=  IPv4Header(
            length=IP_HEADER_LEN+ICMP_HEADER_LEN+len(pkt), # IP + ICMP + pkt
            ttl=IPV4_TTL_DEFAULT, 
            protocol=IPPROTO_ICMP, 
            checksum=0, 
            src=pkt_ipv4_header.dst,  # swap dst and src
            dst=pkt_ipv4_header.src
        )
        icmp_packet = ICMPHeader(type=3, code=3, checksum=0)
        self.send_packet(ipv4_header.to_bytes() + icmp_packet.to_bytes() + pkt)

    def no_socket_tcp(self, pkt: bytes) -> None:
        """Send TCP packet with only the RST flag set."""
        # create a new IPv4 header using the pkt's src and dst
        pkt_ipv4_header = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        ipv4_header=  IPv4Header(
            length=TCPIP_HEADER_LEN+len(pkt), # IP + TCP + pkt
            ttl=IPV4_TTL_DEFAULT, 
            protocol=IPPROTO_TCP, 
            checksum=pkt_ipv4_header.checksum, 
            src=pkt_ipv4_header.dst,  # swap dst and src
            dst=pkt_ipv4_header.src
        )

        # get pkt's tcp, swap the ports, and change flag to RST
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        tcp_hdr.sport, tcp_hdr.dport = tcp_hdr.dport, tcp_hdr.sport
        tcp_hdr.flags = TCP_FLAGS_RST
        
        self.send_packet(ipv4_header.to_bytes() + tcp_hdr.to_bytes() + pkt)
