"""TCP Socket."""
from __future__ import annotations

import asyncio
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

from buffer import TCPSendBuffer, TCPReceiveBuffer

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
            notify_on_data_func: callable,
            socket_cls: type=None,
            fast_retransmit: bool=False, initial_cwnd: int=1000,
            mss: int=1000,
            congestion_control: str='none') -> TCPListenerSocket:

        # These are all vars that are saved away for instantiation of TCPSocket
        # objects when new connections are created.
        self._local_addr = local_addr
        self._local_port = local_port
        self._handle_new_client = handle_new_client_func

        self._send_ip_packet_func = send_ip_packet_func
        self._notify_on_data_func = notify_on_data_func
        if socket_cls is None:
            socket_cls = TCPSocket
        self._socket_cls = socket_cls

        self._fast_retransmit = fast_retransmit
        self._initial_cwnd = initial_cwnd
        self._mss = mss
        self._congestion_control = congestion_control

    def handle_packet(self, pkt: bytes) -> None:
        """
        On new TCP connection request, instantiate new TCPSocket with a tuple
        that uniquely maps to its own TCPSocket instance and has state of LISTEN.
        Then, call handle_packet() on that newly created socket.
        """
        ip_hdr = IPv4Header.from_bytes(pkt[:IP_HEADER_LEN])
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        data = pkt[TCPIP_HEADER_LEN:]

        if tcp_hdr.flags & TCP_FLAGS_SYN:
            sock = self._socket_cls(self._local_addr, self._local_port,
                    ip_hdr.src, tcp_hdr.sport,
                    TCP_STATE_LISTEN,
                    send_ip_packet_func=self._send_ip_packet_func,
                    notify_on_data_func=self._notify_on_data_func,
                    fast_retransmit=self._fast_retransmit,
                    initial_cwnd=self._initial_cwnd, mss=self._mss,
                    congestion_control=self._congestion_control)

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
            notify_on_data_func: callable,
            fast_retransmit: bool=False, initial_cwnd: int=1000,
            mss: int=1000,
            congestion_control: str='none') -> TCPSocket:

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

        # The largest sequence number that has been acknowledged so far.  This
        # is the next sequence number expected be be received by the remote
        # side.
        self.seq = self.base_seq_self + 1

        # The acknowledgment number to send with any packet.  This represents
        # the largest in-order sequence number not yet received.
        self.ack = None

        self.ssthresh = 64000

        # The maximum segment size (MSS), which represents the maximum number
        # of bytes that may be transmitted in a single TCP segment.
        self.mss = mss

        # The congestion window (cwnd), which represents the total number of
        # bytes that may be outstanding (unacknowledged) at one time
        self.cwnd = initial_cwnd
        self.cwnd_inc = self.cwnd

        self.congestion_control = congestion_control

        # Send, receive, and ready buffers.  The send buffer is initialized
        # with our base sequence number.  The receive buffer is initialized
        # with the base sequence number of the remote side.  The ready buffer
        # is what is tapped into when recv() is called on the socket.
        self.send_buffer = TCPSendBuffer(self.base_seq_self + 1) 
        self.receive_buffer = None
        self.ready_buffer = b''

        # The number of duplicate acknowledgments
        self.num_dup_acks = 0
        self.last_ack = 0

        # Timeout duration in seconds
        self.timeout = 1

        # Active time instance (Event instance or None)
        self.timer = None

        # Whether or not we support fast_retransmit (boolean)
        self.fast_retransmit = fast_retransmit


    @classmethod
    def connect(cls, local_addr: str, local_port: int,
            remote_addr: str, remote_port: int,
            send_ip_packet_func: callable,
            notify_on_data_func: callable,
            fast_retransmit: bool=False, initial_cwnd: int=1000,
            mss: int=1000,
            congestion_control: str='none') -> TCPSocketBase:
        sock = cls(local_addr, local_port,
                remote_addr, remote_port,
                TCP_STATE_CLOSED,
                send_ip_packet_func, notify_on_data_func,
                fast_retransmit=fast_retransmit,
                initial_cwnd=initial_cwnd, mss=mss,
                congestion_control=congestion_control)

        sock.initiate_connection()

        return sock

    def bypass_handshake(self, base_seq_self: int, base_seq_other: int):
        '''
        Bypass the TCP three-way handshake.  Allocate a TCPReceiveBuffer
        instance, and initialize it with the base sequence number of the peer
        on the other side of the connection.

        Normally this is done in in handle_syn() (after the SYN is received)
        for the server and in handle_synack() (after the SYNACK is received) in
        the client.
        '''
        self.base_seq_self = base_seq_self
        self.seq = base_seq_self + 1
        self.send_buffer = TCPSendBuffer(self.base_seq_self + 1)

        self.base_seq_other = base_seq_other
        self.ack = base_seq_other + 1
        self.receive_buffer = TCPReceiveBuffer(self.base_seq_other + 1)

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
            
            # initialize the buffers
            self.seq = self.base_seq_self + 1
            self.send_buffer = TCPSendBuffer(self.base_seq_self + 1)

            self.ack = self.base_seq_other + 1
            self.receive_buffer = TCPReceiveBuffer(self.base_seq_other + 1)            

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

            # initialize the buffers
            self.seq = self.base_seq_self + 1
            self.send_buffer = TCPSendBuffer(self.base_seq_self + 1)

            self.ack = self.base_seq_other + 1
            self.receive_buffer = TCPReceiveBuffer(self.base_seq_other + 1)
            
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
        
    def relative_seq_other(self, seq: int) -> int:
        '''
        Return the specified sequence number (int) relative to the base
        sequence number for the other side of the connection.

        seq: An int value to be made relative to the base sequence number.
        '''

        return seq - self.base_seq_other


    def relative_seq_self(self, seq: int) -> int:
        '''
        Return the specified sequence number (int) relative to our base
        sequence number.

        seq: An int value to be made relative to the base sequence number.
        '''

        return seq - self.base_seq_self

    def send_if_possible(self) -> int:
        """
        Grabs segments of data from its TCPSendBuffer and sends them 
        to the TCP peer.
        """
        # send segments of data until the number of outstanding bytes exceeds the congestion window.
        while self.send_buffer.bytes_outstanding() < self.cwnd and self.send_buffer.bytes_not_yet_sent():
            # Grab data from TCPSendBuffer
            data, seq = self.send_buffer.get(self.mss)
            self.send_packet(seq=seq, ack=self.ack, flags=0, data=data)
            if not self.timer: 
                # start timer if not already set
                self.start_timer()

    def send(self, data: bytes) -> None:
        self.send_buffer.put(data)
        self.send_if_possible()

    def recv(self, num: int) -> bytes:
        data = self.ready_buffer[:num]
        self.ready_buffer = self.ready_buffer[num:]
        return data

    def handle_data(self, pkt: bytes) -> None:
        """
        Extracts segment data and sequence number from TCP packet.

        Args:
            pkt : byte
                an IP packet with IP header.
        """
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        data = pkt[TCPIP_HEADER_LEN:]

        # put the longest contiguous set of bytes and store in ready buffer
        self.receive_buffer.put(data, tcp_hdr.seq)
        receive_data, receive_seq = self.receive_buffer.get()

        # send ack with next expected in-order byte
        self.ack = receive_seq + len(receive_data)
        self.send_ack()

        if len(receive_data):
            # if new data was recieved, add to ready_buffer and notify application
            self.ready_buffer += receive_data
            self._notify_on_data()
        

    def handle_ack(self, pkt: bytes) -> None:
        """
        Bytes previously sent are acknowledgxed. Check the ack number
        in the TCP header and acknowledge any new data by sliding the window.

        Args:
            pkt : bytes
                an IP packet with IP header.
        """
        # check acknowledgement number in the TCP header and slide the window
        tcp_hdr = TCPHeader.from_bytes(pkt[IP_HEADER_LEN:TCPIP_HEADER_LEN])
        self.send_buffer.slide(tcp_hdr.ack)

        if self.fast_retransmit:
            # track the number of duplicate ACKs. 
            if self.seq == tcp_hdr.ack:
                self.num_dup_acks += 1
            else:
                self.num_dup_acks = 0

            if self.num_dup_acks == 3:
                # ignore addutional acks
                self.retransmit()
                # don't do anything with the timer
                return
            
        # Adjust congestion window
        if self.congestion_control == 'tahoe':
            bytes_acked = tcp_hdr.ack - self.seq
            if self.cwnd < self.ssthresh:
                # slow start: increment cwnd by the number of new bytes received
                self.set_cwnd(self.cwnd + self.cwnd_inc + bytes_acked)            
            else:
                # congestion avoidance (additive increase)
                prev_cwd = self.cwnd + self.cwnd_inc
                self.set_cwnd(prev_cwd + int(bytes_acked * self.mss / prev_cwd))
            
        
        self.cancel_timer()

        if self.send_buffer.bytes_outstanding():
            # restart timer if we're still waiting for acks. 
            if not self.timer: 
                self.start_timer()

        self.send_if_possible()
        self.seq = tcp_hdr.ack # the byte the client is expecting
                

    def retransmit(self) -> None:
        """
        Grab the oldest unacknowledged segment from the buffer and retransmit it 
        """
        # adjust congestion window
        if self.congestion_control == 'tahoe':
            self.multiplicative_decrease()
            
        data, seq = self.send_buffer.get_for_resend(self.mss)
        if len(data):
            self.cancel_timer()
            self.send_packet(seq=seq, ack=self.ack, flags=0, data=data)
            self.start_timer()

    def start_timer(self) -> None:
        loop = asyncio.get_event_loop()
        self.timer = loop.call_later(self.timeout, self.retransmit)

    def cancel_timer(self):
        if not self.timer:
            return
        self.timer.cancel()
        self.timer = None

    def send_ack(self):
        self.send_packet(self.seq, self.ack, TCP_FLAGS_ACK)

    def set_cwnd(self, cwnd: int) -> None:
        """Sets the cwnd such that self.cwnd is always a multiple of self.mss and the remainder in self.cwnd_inc"""
        self.cwnd = int(cwnd / self.mss) * self.mss
        self.cwnd_inc = cwnd % self.mss

    def multiplicative_decrease(self) -> None:
        """When a loss event occurs, decrease ssthresh to half of cwnd (minimum of mss) and cwnd should be 1 mss."""
        self.ssthresh = max(self.cwnd/2, self.mss) 
        self.set_cwnd(self.mss)