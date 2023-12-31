from __future__ import annotations

import random

TCP_FLAGS_SYN = 0x02
TCP_FLAGS_RST = 0x04
TCP_FLAGS_ACK = 0x10

TCP_STATE_LISTEN = 0
TCP_STATE_SYN_SENT = 1
TCP_STATE_SYN_RECEIVED = 2
TCP_STATE_ESTABLISHED = 3
TCP_STATE_FIN_WAIT_1 = 4
TCP_STATE_FIN_WAIT_2 = 5
TCP_STATE_CLOSE_WAIT = 6
TCP_STATE_CLOSING = 7
TCP_STATE_LAST_ACK = 8
TCP_STATE_TIME_WAIT = 9
TCP_STATE_CLOSED = 10

from headers import IPv4Header, UDPHeader, TCPHeader, \
        IP_HEADER_LEN, UDP_HEADER_LEN, TCP_HEADER_LEN, \
        TCPIP_HEADER_LEN, UDPIP_HEADER_LEN


#From /usr/include/linux/in.h:
IPPROTO_TCP = 6 # Transmission Control Protocol
IPPROTO_UDP = 17 # User Datagram Protocol

IPV4_TTL_DEFAULT = 64 # as instructed



class UDPSocket:
    """
    A socket that has its address and port bind to it
    """
    def __init__(self, local_addr: str, local_port: int,
            send_ip_packet_func: callable,
            notify_on_data_func: callable) -> UDPSocket:

        self._local_addr = local_addr
        self._local_port = local_port
        # sends an IP datagram out of one of its host's interface
        self._send_ip_packet = send_ip_packet_func 
        # let's the application know there is data
        self._notify_on_data = notify_on_data_func 

        self.buffer = []

    def handle_packet(self, pkt: bytes) -> None:
        """
        Parses a packet, appends the data to the buffer with the remote 
        IP address and port it came from, and notifies the application that 
        there's data to be read.
        """
        # parse the packet
        ipv4_header = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        udp_header = UDPHeader.from_bytes(pkt[IP_HEADER_LEN:UDPIP_HEADER_LEN])
        data = pkt[UDPIP_HEADER_LEN:]

        # (data, address, port) address and port should be where it came from
        self.buffer.append((data, ipv4_header.src, udp_header.sport))
        self._notify_on_data()

    @classmethod
    def create_packet(cls, src: str, sport: int, dst: str, dport: int,
            data: bytes=b'') -> bytes:
        """Creates a UDP datagram packet as a byte instance."""
        ip_header = IPv4Header(
            length=(UDPIP_HEADER_LEN+len(data)), 
            ttl=IPV4_TTL_DEFAULT, 
            protocol=IPPROTO_UDP, 
            checksum=0, 
            src=src, 
            dst=dst
        )

        udp_header = UDPHeader(
            sport=sport, 
            dport=dport, 
            length=UDP_HEADER_LEN+len(data), 
            checksum=0
        )
        return ip_header.to_bytes() + udp_header.to_bytes() + data

    def send_packet(self, remote_addr: str, remote_port: int,
            data: bytes) -> None:
        """Creates and sends a UDP datagram"""
        self._send_ip_packet(
            self.create_packet(
                src=self._local_addr, 
                sport=self._local_port, 
                dst=remote_addr, 
                dport=remote_port, 
                data=data)
        )

    def recvfrom(self) -> tuple[bytes, str, int]:
        """
        Called by the application to receieve data. Returns the
        contents of the earliest recieved UDP datagram that has not been read
        """
        return self.buffer.pop(0)

    def sendto(self, data: bytes, remote_addr: str, remote_port: int) -> None:
        """Called by the application to send data."""
        self.send_packet(remote_addr, remote_port, data)


class TCPSocketBase:
    def handle_packet(self, pkt: bytes) -> None:
        pass

class TCPListenerSocket(TCPSocketBase):
    """Handles packets that are for new TCP connection requests. Instantiates new TCPSocket with each request."""
    def __init__(self, local_addr: str, local_port: int,
            handle_new_client_func: callable, send_ip_packet_func: callable,
            notify_on_data_func: callable) -> TCPListenerSocket:

        # These are all vars that are saved away for instantiation of TCPSocket
        # objects when new connections are created.
        self._local_addr = local_addr
        self._local_port = local_port
        self._handle_new_client = handle_new_client_func

        self._send_ip_packet_func = send_ip_packet_func
        self._notify_on_data_func = notify_on_data_func


    def handle_packet(self, pkt: bytes) -> None:
        """
        On new TCP connection request, instantiate new TCPSocket with a tuple
        that uniquely maps to its own TCPSocket instance and has state of LISTEN.
        Then, call handle_packet() on that newly created socket.
        """
        ip_hdr = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        data = pkt[TCPIP_HEADER_LEN:]

        sock = TCPSocket(self._local_addr, self._local_port,
                ip_hdr.src, tcp_hdr.sport,
                TCP_STATE_LISTEN,
                send_ip_packet_func=self._send_ip_packet_func,
                notify_on_data_func=self._notify_on_data_func)
        if tcp_hdr.flags & TCP_FLAGS_SYN:
            self._handle_new_client(self._local_addr, self._local_port,
                    ip_hdr.src, tcp_hdr.sport, sock)

            sock.handle_packet(pkt)
        else:
            # when a TCP packet reaches a socket in the LISTEN state,
            # but the packet does not have the SYN flag set, 
            # return a TCP packet with only the RST flag set.
            sock.send_reset_packet(pkt)

class TCPSocket(TCPSocketBase):
    def __init__(self, local_addr: str, local_port: int,
            remote_addr: str, remote_port: int, state: int,
            send_ip_packet_func: callable,
            notify_on_data_func: callable) -> TCPSocket:

        # The local/remote address/port information associated with this
        # TCPConnection
        self._local_addr = local_addr
        self._local_port = local_port
        self._remote_addr = remote_addr
        self._remote_port = remote_port

        # The current state (TCP_STATE_LISTEN, TCP_STATE_CLOSED, etc.)
        self.state = state

        # Helpful methods for helping us send IP packets and
        # notifying the application that we have received data.
        self._send_ip_packet = send_ip_packet_func
        self._notify_on_data = notify_on_data_func

        # Base sequence number
        self.base_seq_self = self.initialize_seq()

        # Base sequence number for the remote side
        self.base_seq_other = None


    @classmethod
    def connect(cls, local_addr: str, local_port: int,
            remote_addr: str, remote_port: int,
            send_ip_packet_func: callable,
            notify_on_data_func: callable) -> TCPSocket:
        sock = cls(local_addr, local_port,
                remote_addr, remote_port,
                TCP_STATE_CLOSED,
                send_ip_packet_func, notify_on_data_func)

        sock.initiate_connection()

        return sock


    def handle_packet(self, pkt: bytes) -> None:
        ip_hdr = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        data = pkt[TCPIP_HEADER_LEN:]

        if self.state != TCP_STATE_ESTABLISHED:
            # establish 3 way handshake
            self.continue_connection(pkt)

        if self.state == TCP_STATE_ESTABLISHED:
            if data:
                # handle data
                self.handle_data(pkt)
            if tcp_hdr.flags & TCP_FLAGS_ACK:
                # handle ACK
                self.handle_ack(pkt)


    def initialize_seq(self) -> int:
        return random.randint(0, 65535)


    def initiate_connection(self) -> None:
        """Initiate the TCP heandshake."""
        # send TCP packet with SYN flag set
        self.send_packet(
            seq=self.base_seq_self, 
            ack=0, # SYN packets don't have an acknolwedgement number
            flags= TCP_FLAGS_SYN,
            data=b'',
        )

        # transition state to SYN_SENT
        self.state=TCP_STATE_SYN_SENT

    def handle_syn(self, pkt: bytes) -> None:
        """Handle SYN packet"""
        tcp_header = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        
        if (tcp_header.flags & TCP_FLAGS_SYN) == TCP_FLAGS_SYN:
            # save base sequence of remote side
            self.base_seq_other = tcp_header.seq
            # send corresponding SYNACK packet
            self.send_packet(
                seq=self.base_seq_self, 
                ack=self.base_seq_other + 1,
                flags= TCP_FLAGS_SYN | TCP_FLAGS_ACK,
                data=pkt[TCPIP_HEADER_LEN:],
            )

            # transition state
            self.state = TCP_STATE_SYN_RECEIVED
        else:
            # if flag is not SYN, return a TCP packet with only the RST flag set
            self.send_reset_packet(pkt)

    def handle_synack(self, pkt: bytes) -> None:
        """Handle TCP SYNACK packet"""

        tcp_header = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        synack_flag = TCP_FLAGS_SYN | TCP_FLAGS_ACK
        
        # ignore packet if flag is not SYNACK or the ack field is not our current sequence
        if (tcp_header.flags & synack_flag) == synack_flag and tcp_header.ack == self.base_seq_self + 1:
            # save base sequence of remote side
            self.base_seq_other = tcp_header.seq

            # send corresponding ACK packet
            self.send_packet(
                seq=self.base_seq_self + 1, 
                ack=self.base_seq_other + 1,
                flags= TCP_FLAGS_ACK,
                data=pkt[TCPIP_HEADER_LEN:],
            )

            # transition state
            self.state = TCP_STATE_ESTABLISHED

    def handle_ack_after_synack(self, pkt: bytes) -> None:
        """Handle incoming TCP ACK packet."""
        tcp_header = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        
        # ignore the packet if not ACK flag or if ack field is not our sequence number
        if (tcp_header.flags & TCP_FLAGS_ACK) == TCP_FLAGS_ACK and tcp_header.ack == self.base_seq_self+1:
            self.state = TCP_STATE_ESTABLISHED


    def continue_connection(self, pkt: bytes) -> None:
        """Handle the connection states"""
        if self.state == TCP_STATE_LISTEN:
            self.handle_syn(pkt)
        elif self.state == TCP_STATE_SYN_SENT:
            self.handle_synack(pkt)
        elif self.state == TCP_STATE_SYN_RECEIVED:
            self.handle_ack_after_synack(pkt)

    def send_data(self, data: bytes, flags: int=0) -> None:
        pass

    @classmethod
    def create_packet(cls, src: str, sport: int, dst: str, dport: int,
            seq: int, ack: int, flags: int, data: bytes=b'') -> bytes:
        """Creates a TCP packet as a byte instance."""
        ip_header = IPv4Header(
            length=(TCPIP_HEADER_LEN+len(data)), 
            ttl=IPV4_TTL_DEFAULT, 
            protocol=IPPROTO_TCP, 
            checksum=0, 
            src=src, 
            dst=dst
        )

        tcp_header = TCPHeader(
            sport=sport, 
            dport=dport, 
            seq=seq,
            ack=ack,
            flags=flags,
            checksum=0
        )

        return ip_header.to_bytes() + tcp_header.to_bytes() + data

    def send_packet(self, seq: int, ack: int, flags: int,
            data: bytes=b'') -> None:
        """Creates and sends a TCP packet"""
        self._send_ip_packet(
            self.create_packet(
                src=self._local_addr,
                sport=self._local_port,
                dst=self._remote_addr,
                dport=self._remote_port,
                seq=seq,
                ack=ack,
                flags=flags,
                data=data,
            )
        )

    def send_reset_packet(self, pkt: bytes) -> None:
        """Creates and sends a reset TCP packet"""
        self.send_packet(
            seq=self.base_seq_self,
            ack=0, # no data has been acknolwedged
            flags= TCP_FLAGS_RST,
            data=pkt[TCPIP_HEADER_LEN:],
        )

    def handle_data(self, pkt: bytes) -> None:
        pass

    def handle_ack(self, pkt: bytes) -> None:
        pass
