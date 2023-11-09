#!/usr/bin/python3

import argparse
import asyncio
import os
import socket
import sys
import struct

from cougarnet.sim.host import BaseHost
from cougarnet.util import \
        mac_str_to_binary, mac_binary_to_str, \
        ip_str_to_binary, ip_binary_to_str

from forwarding_table import ForwardingTable

ETH_HDR_LEN = 14

# From /usr/include/linux/if_ether.h:
ETH_P_IP = 0x0800 # Internet Protocol packet
ETH_P_ARP = 0x0806 # Address Resolution packet

# From /usr/include/net/if_arp.h:
ARPHRD_ETHER = 1 # Ethernet 10Mbps
ARPOP_REQUEST = 1 # ARP request
ARPOP_REPLY = 2 # ARP reply

# From /usr/include/linux/in.h:
IPPROTO_ICMP = 1 # Internet Control Message Protocol
IPPROTO_TCP = 6 # Transmission Control Protocol
IPPROTO_UDP = 17 # User Datagram Protocol

class EthernetHeader:
    def __init__(self, dmac: str, smac: str, ether_type: int):
        """
        Represents a Ethernet header.

        Args:
            dmac: str
                destination MAC address
            smac : int
                source MAC address
            ether_type : int
                ethernet protocol types (hexnumber)
        """
        self.dmac = dmac.lower()
        self.smac = smac.lower()
        self.ether_type = ether_type

    def __repr__(self) -> str:
        return f'EthernetHeader(dmac={self.dmac}, smac={self.smac}, ether_type={self.ether_type})'

    def __str__(self) -> str:
        return repr(self)
    
    @classmethod
    def from_bytes(cls, hdr: bytes):
        """
        Initialize a EthernetHeader from raw byte instance
        """
        dmac = mac_binary_to_str(hdr[:6])
        smac = mac_binary_to_str(hdr[6:12])
        ether_type, = struct.unpack('!H', hdr[12:14])

        return cls(dmac, smac, ether_type)

    def to_bytes(self) -> bytes:
        """
        Return bytes of this EthernetHeader instance with some defaults. 
        """
        return mac_str_to_binary(self.dmac) + mac_str_to_binary(self.smac) + struct.pack('!H', self.ether_type)

class ARPPacket:
    def __init__(self, 
                 operation_code: int, 
                 src_hw_addr: bytes, 
                 src_protocol_addr: bytes, 
                 dest_hw_addr: bytes, 
                 dest_protocol_addr: bytes, 
                 hw_type: int = ARPHRD_ETHER, 
                 protocol_type: int = ETH_P_IP,
                 hw_length: int = 6,
                 protocol_length: int = 4,
    ): 
        """
        Represents a ARP packet. Defaults to MAC and IP as hardware and protocol.

        Args:
            operation_code : int 
                The operation or opcode will be a request (1) or reply (2). 
            src_hw_addr : bytes
                The source hardware address. Length must match the value of hardware address length.
            src_protocol_addr : bytes
                The source protcol address. Length must match the value of the protocol address length.
            dest_hw_addr : bytes
                The destination hardware address. Length must match the value of hardware address length.
            dest_protocol_addr : bytes
                The destination protcol address. Length must match the value of the protocol address length.
            hw_type : int
                The hardware type
            protocol_type : int
                The protocol type
            hw_length : int
                The hardware address length. Defaults to 6 because MAC addresses are always 6 bytes long.
            protocol_length : int
                The protocol address length. Defaults to 4 because IPv4 addresses are 4 bytes long.
        """
        assert len(src_hw_addr) == hw_length, f'Length of src_hw_addr={src_hw_addr} must match the value of the hardware address length ({hw_length})'
        assert len(dest_hw_addr) == hw_length, f'Length of dest_hw_addr={dest_hw_addr} must match the value of the hardware address length ({hw_length})'
        assert len(src_protocol_addr) == protocol_length, f'Length of src_protocol_addr={src_protocol_addr} must match the value of the protocol address length ({protocol_length})'
        assert len(dest_protocol_addr) == protocol_length, f'Length of dest_protocol_addr={dest_protocol_addr} must match the value of the protocol address length ({protocol_length})'
        

        self.operation_code = operation_code
        self.src_hw_addr = src_hw_addr
        self.src_protocol_addr = src_protocol_addr
        self.dest_hw_addr = dest_hw_addr
        self.dest_protocol_addr = dest_protocol_addr
        self.hw_type = hw_type
        self.protocol_type = protocol_type
        self.hw_length = hw_length
        self.protocol_length = protocol_length

    @classmethod
    def from_bytes(cls, pkt: bytes):
        """
        Initialize a ARPPacket from raw byte instance.
        """
        hw_type, protocol_type, hw_length, protocol_length, operation_code = struct.unpack("!HHBBH", pkt[:8])
        src_hw_addr = pkt[8:8+hw_length]
        src_protocol_addr = pkt[8+hw_length:8+hw_length+protocol_length]
        dest_hw_addr = pkt[8+hw_length+protocol_length:8+2*hw_length+protocol_length]
        dest_protocol_addr = pkt[8+2*hw_length+protocol_length:8+2*hw_length+2*protocol_length]

        return cls(
            operation_code = operation_code,
            src_hw_addr = src_hw_addr,
            src_protocol_addr = src_protocol_addr,
            dest_hw_addr = dest_hw_addr,
            dest_protocol_addr = dest_protocol_addr,
            hw_type = hw_type,
            protocol_type = protocol_type,
            hw_length = hw_length,
            protocol_length = protocol_length,
        )

    def to_bytes(self) -> bytes:
        """
        Return bytes of this ARPPacket instance. 
        """
        return struct.pack(f"!HHBBH{self.hw_length}s{self.protocol_length}s{self.hw_length}s{self.protocol_length}s",
                                 self.hw_type, self.protocol_type,
                                 self.hw_length, self.protocol_length, self.operation_code,
                                 self.src_hw_addr,
                                 self.src_protocol_addr,
                                 self.dest_hw_addr,
                                 self.dest_protocol_addr,
                            )

    
class Host(BaseHost):
    def __init__(self, ip_forward: bool):
        super().__init__()

        self._ip_forward = ip_forward
        self._arp_table = {}
        self.pending = []

    def _handle_frame(self, frame: bytes, intf: str) -> None:
        """
        Handles an Ethernet frame

        Args:
            frame : bytes
                The Ethernet frame received
            intf : str
                The interface on which it was received
        """
        eth_hdr = EthernetHeader.from_bytes(frame[:ETH_HDR_LEN])
        payload = frame[ETH_HDR_LEN:]

        intf_mac_address = self.int_to_info[intf].mac_addr
        # if the frame's MAC destination is this interface or a broadcast address, then process it
        if (eth_hdr.dmac == intf_mac_address or eth_hdr.dmac == "ff:ff:ff:ff:ff:ff"):
            if eth_hdr.ether_type == ETH_P_IP:
                self.handle_ip(payload, intf)
            elif eth_hdr.ether_type == ETH_P_ARP:
                self.handle_arp(payload, intf)
            # don't do anything if it is any other type
        else:
            self.not_my_frame(frame, intf)

    def handle_ip(self, pkt: bytes, intf: str) -> None:
        pass

    def handle_tcp(self, pkt: bytes) -> None:
        pass

    def handle_udp(self, pkt: bytes) -> None:
        pass

    def handle_arp(self, pkt: bytes, intf: str) -> None:
        """
        Determines whether the ARP packet is a ARP request or response and handles it accordingly
        
        Args:
            `pkt` : bytes
                The ARP packet recieved
            `intf : str
                The interface on which it was received
        """
        arp_pkt = ARPPacket.from_bytes(pkt)
        self.handle_arp_request(pkt, intf) if arp_pkt.operation_code == ARPOP_REQUEST else self.handle_arp_response(pkt, intf)

    def handle_arp_response(self, pkt: bytes, intf: str) -> None:

        arp_pkt = ARPPacket.from_bytes(pkt)
                
        # udpate ARP table with sender IP to sender MAC
        self._arp_table[ip_binary_to_str(arp_pkt.src_protocol_addr)] = mac_binary_to_str(arp_pkt.src_hw_addr)

        # send all packets in queue whose next hop corresponds to the sender IP address in the response
        packets_to_send = [p for p in self.pending if p[2] == ip_binary_to_str(arp_pkt.src_protocol_addr)]
        for packet, intf, next_hop in packets_to_send:
            ethernet_frame = EthernetHeader(dmac=mac_binary_to_str(arp_pkt.src_hw_addr), smac=self.int_to_info[intf].mac_addr, ether_type=ETH_P_IP).to_bytes() + packet
            self.send_frame(ethernet_frame, intf)

        # remove from queue
        self.pending = [p for p in self.pending if p[2] != ip_binary_to_str(arp_pkt.src_protocol_addr)]


    def handle_arp_request(self, pkt: bytes, intf: str) -> None:
        """Update ARP table and send response if IP destination matches with intf IP."""
        arp_pkt = ARPPacket.from_bytes(pkt)
        
        # udpate ARP table with sender IP to sender MAC
        self._arp_table[ip_binary_to_str(arp_pkt.src_protocol_addr)] = mac_binary_to_str(arp_pkt.src_hw_addr)

        # if the target IP matches the IP of `intf`, then create ARP response and Ethernet frame
        if (ip_binary_to_str(arp_pkt.dest_protocol_addr) == self.int_to_info[intf].ipv4_addrs[0]):
            intf_mac_address = self.int_to_info[intf].mac_addr
            response_pkt = ARPPacket(
                operation_code=ARPOP_REPLY,
                src_hw_addr=mac_str_to_binary(intf_mac_address),
                src_protocol_addr=arp_pkt.dest_protocol_addr,
                dest_hw_addr=arp_pkt.src_hw_addr,
                dest_protocol_addr=arp_pkt.src_protocol_addr,
            )
            eth_frame = EthernetHeader(dmac=mac_binary_to_str(arp_pkt.src_hw_addr), smac=intf_mac_address, ether_type=ETH_P_ARP).to_bytes() + response_pkt.to_bytes()
            self.send_frame(eth_frame, intf)

    def send_packet_on_int(self, pkt: bytes, intf: str, next_hop: str) -> None:
        """
        Finds the MAC address corresponding to `next_hop`, builds ethernet frame, and sends IP packet.

        Args:
            `pkt` : bytes
                An IP packet with IPv4 IP header.
            `intf` : str
                The name of an interface on the host, on which the packet will be sent
            `next_hop` : str
                The IP address of the next hop (IP destination if on the same subnet
                as the host or the IP address of a router) for the packet. 
        """
        print(f'Attempting to send packet on {intf} with next hop {next_hop}:\n{repr(pkt)}')
        
        src_mac_addr = self.int_to_info[intf].mac_addr
        # try to find the MAC address corresponding to `next_hop`
        if (dmac := self._arp_table.get(next_hop)):
            # if host-wide ARP table has mapping, then build the ethernet frame and send it
            ethernet_frame = EthernetHeader(dmac=dmac, smac=src_mac_addr, ether_type=ETH_P_IP).to_bytes() + pkt
            self.send_frame(ethernet_frame, intf)
        else:
            # if no mapping exists, queue the packet for later sending, create ARP request, then build and send ethernet frame
            self.pending.append((pkt, intf, next_hop)) # will send the IP packet later
            arp_pkt = ARPPacket(
                operation_code=ARPOP_REQUEST,
                src_hw_addr=mac_str_to_binary(src_mac_addr),
                src_protocol_addr=ip_str_to_binary(self.int_to_info[intf].ipv4_addrs[0]),
                dest_hw_addr=mac_str_to_binary("00:00:00:00:00:00"),
                dest_protocol_addr=ip_str_to_binary(next_hop),
            )
            ethernet_frame = EthernetHeader(dmac="ff:ff:ff:ff:ff:ff", smac=src_mac_addr, ether_type=ETH_P_ARP).to_bytes() + arp_pkt.to_bytes()
            self.send_frame(ethernet_frame, intf)

    def send_packet(self, pkt: bytes) -> None:
        print(f'Attempting to send packet:\n{repr(pkt)}')

    def forward_packet(self, pkt: bytes) -> None:
        pass

    def not_my_frame(self, frame: bytes, intf: str) -> None:
        pass

    def not_my_packet(self, pkt: bytes, intf: str) -> None:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--router', '-r',
            action='store_const', const=True, default=False,
            help='Act as a router by forwarding IP packets')
    args = parser.parse_args(sys.argv[1:])

    Host(args.router).run()

if __name__ == '__main__':
    main()
