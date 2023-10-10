from __future__ import annotations

import struct

from cougarnet.util import \
        ip_str_to_binary, ip_binary_to_str


IP_HEADER_LEN = 20
UDP_HEADER_LEN = 8
TCP_HEADER_LEN = 20
TCPIP_HEADER_LEN = IP_HEADER_LEN + TCP_HEADER_LEN
UDPIP_HEADER_LEN = IP_HEADER_LEN + UDP_HEADER_LEN

TCP_RECEIVE_WINDOW = 64

class IPv4Header:
    def __init__(self, length: int, ttl: int, protocol: int, checksum: int,
        src: str, dst: str) -> IPv4Header:
        """
        Represents a IPv4 header.

        Attr:
            length: int
                length of the entire IP datagram including IP header and payload
            ttl : int
                time-to-live value
            protocol : int
                the protocol associated with the next header        
            checksum : int
                the checksum of the IPv4 header
            src : str
                the source IP address
            dst : str
                the destination IP address
        """
        self.length = length
        self.ttl = ttl
        self.protocol = protocol
        self.checksum = checksum
        self.src = src
        self.dst = dst

    def __repr__(self) -> str:
        return f'IPv4Header(length={self.length}, ttl={self.ttl}, protcol={self.protocol}, checksum={self.checksum}, src="{self.src}", dst="{self.dst}")'

    def __str__(self) -> str:
        return repr(self)
    
    @classmethod
    def from_bytes(cls, hdr: bytes) -> IPv4Header:
        """
        Initialize a IPv4 from raw byte instance
        """
        length, = struct.unpack('!H', hdr[2:4])
        ttl, = struct.unpack('!B', hdr[8:9])
        protocol, = struct.unpack('!B', hdr[9:10])
        checksum, = struct.unpack('!H', hdr[10:12])
        src = ip_binary_to_str(hdr[12:16])
        dst = ip_binary_to_str(hdr[16:20])
        
        return cls(length=length, ttl=ttl, protocol=protocol, checksum=checksum, src=src, dst=dst)

    def to_bytes(self) -> bytes:
        """
        Return bytes of this IPv4 instance with some defaults. 
        """
        hdr = b''
        hdr += struct.pack('!B', 0b01000101) # version (always 4) and IHL (always 5)
        hdr += struct.pack('!B', 0) # differentiated services (always 0)
        hdr += struct.pack('!H', self.length) 
        hdr += struct.pack('!I', 0) # identification, flags, fragment offset (N/A, so 0)
        hdr += struct.pack('!B', self.ttl)
        hdr += struct.pack('!B', self.protocol)
        hdr += struct.pack('!H', self.checksum)
        hdr += struct.pack('!I', int.from_bytes(ip_str_to_binary(self.src)))
        hdr += struct.pack('!I', int.from_bytes(ip_str_to_binary(self.dst)))

        return hdr


class UDPHeader:
    """
    Represents a UDP header.

    Attr:
        sport : int
            source port
        dport : int
            destination port
        length : int
            length of the entire UDP diagram, including UDP header and payload
        checksum : int
            checksum of a pseudo IPv4 header. (0 can be used)
    """
    def __init__(self, sport: int, dport: int, length: int,
            checksum: int) -> UDPHeader:
        self.sport = sport
        self.dport = dport
        self.checksum = checksum
        self.length = length

    @classmethod
    def from_bytes(cls, hdr: bytes) -> UDPHeader:
        """
        Initialize a UDPHeader from raw byte instance
        """
        sport, = struct.unpack('!H', hdr[:2])
        dport, = struct.unpack('!H', hdr[2:4])
        length, = struct.unpack('!H', hdr[4:6])
        checksum, = struct.unpack('!H', hdr[6:8])
        return cls(sport, dport, length, checksum)

    def to_bytes(self) -> bytes:
        """
        Return bytes of this UDPHeader instance.
        """
        hdr = b''
        hdr += struct.pack('!H', self.sport)
        hdr += struct.pack('!H', self.dport)
        hdr += struct.pack('!H', self.length)
        hdr += struct.pack('!H', self.checksum)
        return hdr


class TCPHeader:
    def __init__(self, sport: int, dport: int, seq: int, ack: int,
            flags: int, checksum: int) -> TCPHeader:
        """
        Represents a TCP header.

        Attr:
            sport: int
                source port
            dport : int
                destination port
            seq : int
                sequence number
            ack : int
                acknowledgement number
            flags : int
                control bits (flags can be URG, ACK, PSH, RST, SYN, or FIN)
            checksum : int            
                checksum of a pseudo IPv4 header (N/A in this lab)
        """
        self.sport = sport
        self.dport = dport
        self.seq = seq
        self.ack = ack
        self.flags = flags
        self.checksum = checksum

    def __repr__(self) -> str:
        return f'TCPHeader(sport={self.sport}, dport={self.dport}, seq={self.seq}, ack={self.ack}, flags={self.flags}, checksum={self.checksum})'

    def __str__(self) -> str:
        return repr(self)
    
    @classmethod
    def from_bytes(cls, hdr: bytes) -> TCPHeader:
        """
        Initialize a TCPHeader from raw byte instance
        """
        sport, = struct.unpack('!H', hdr[0:2])
        dport, = struct.unpack('!H', hdr[2:4])
        seq, = struct.unpack('!I', hdr[4:8])
        ack, = struct.unpack('!I', hdr[8:12])

        # get the control bits (6 bits)
        flag_data, = struct.unpack('!B', hdr[13:14])
        flags = flag_data & 0b111111

        checksum, = struct.unpack('!H', hdr[16:18])

        return cls(sport, dport, seq, ack, flags, checksum)

    def to_bytes(self) -> bytes:
        """
        Return bytes of this TCPHeader instance with some defaults. 
        """
        hdr = b''
        hdr += struct.pack('!H', self.sport) 
        hdr += struct.pack('!H', self.dport)
        hdr += struct.pack('!I', self.seq) 
        hdr += struct.pack('!I', self.ack)
        hdr += struct.pack('!H', 0b0101000000000000 | self.flags) # data offset (always 5), reserved (0), ECN (0), and Control Bits
        hdr += struct.pack('!H', TCP_RECEIVE_WINDOW) # window
        hdr += struct.pack('!H', self.checksum) 
        hdr += struct.pack('!H', 0) 

        return hdr
