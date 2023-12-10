#!/usr/bin/python3

import argparse
import asyncio
import os
import socket
import sys
import struct
import json

from cougarnet.sim.host import BaseHost
from cougarnet.util import \
        mac_str_to_binary, mac_binary_to_str, \
        ip_str_to_binary, ip_binary_to_str

from forwarding_table import ForwardingTable
from scapy.all import Ether, IP, ARP

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

class Host(BaseHost):
    def __init__(self, ip_forward: bool):
        super(Host, self).__init__()

        self._ip_forward = ip_forward
        self._arp_table = {}
        self.pending = []

        self.forwarding_table = ForwardingTable()

        # add each entry in routes into the forwarding table using prefix, intf, and next_hop
        routes = json.loads(os.environ['COUGARNET_ROUTES'])
        for prefix, intf, next_hop in routes:
            self.forwarding_table.add_entry(prefix, intf, next_hop)

        # for each interface, add the ip prefix, the interface itself, and next_hop of none
        for intf in self.physical_interfaces:
            prefix = '%s/%d' % \
                    (self.int_to_info[intf].ipv4_addrs[0],
                            self.int_to_info[intf].ipv4_prefix_len)
            self.forwarding_table.add_entry(prefix, intf, next_hop=None)

    def _handle_frame(self, frame: bytes, intf: str) -> None:
        """
        Handles an Ethernet frame

        Args:
            frame : bytes
                The Ethernet frame received
            intf : str
                The interface on which it was received
        """
        eth = Ether(frame)
        if eth.dst == 'ff:ff:ff:ff:ff:ff' or \
                eth.dst == self.int_to_info[intf].mac_addr:
        # if the frame's MAC destination is this interface or a broadcast address, then process it
            
            if eth.type == ETH_P_IP:
                self.handle_ip(bytes(eth.payload), intf)
            elif eth.type == ETH_P_ARP:
                self.handle_arp(bytes(eth.payload), intf)
        else:
            self.not_my_frame(frame, intf)
        

    def handle_ip(self, pkt: bytes, intf: str) -> None:
        """
        Determine what to do with an IP packet.

        Args:
            pkt: the IP packet received
            intf: the interface on which it was received
        """
        ip = IP(pkt)
        all_addrs = []

        # Parse out all destination IP address in the packet
        for intf1 in self.int_to_info:
            all_addrs += self.int_to_info[intf1].ipv4_addrs

        # Determine if this host is the final destination for the packet, based on the destination IP address
        if ip.dst == '255.255.255.255' or ip.dst in all_addrs:
            #  If the packet is destined for this host, based on the tests in the previous bullet, then call another method to handle the payload, depending on the protocol value in the IP header.
            if ip.proto == IPPROTO_TCP:
                # For type TCP (IPPROTO_TCP = 6), call handle_tcp(), passing the full IP datagram, including header.
                self.handle_tcp(pkt)
            elif ip.proto == IPPROTO_UDP:
                # For type UDP (IPPROTO_UDP = 17), call handle_udp(), passing the full IP datagram, including header. 
                self.handle_udp(pkt)
            # If the protocol is something other than TCP or UDP, ignore it.
        else:
            # If the destination IP address does not match any IP address on the system, and it is not the IP broadcast, then call not_my_packet(), passing it the full IP datagram and the interface on which it arrived.
            self.not_my_packet(pkt, intf)

    def handle_tcp(self, pkt: bytes) -> None:
        print('Handling TCP packet')
        
    def handle_udp(self, pkt: bytes) -> None:
        print('Handling UDP packet')

    def handle_arp(self, pkt: bytes, intf: str) -> None:
        """
        Determines whether the ARP packet is a ARP request or response and handles it accordingly
        
        Args:
            `pkt` : bytes
                The ARP packet recieved
            `intf : str
                The interface on which it was received
        """
        arp = ARP(pkt)
        # Determine whether the ARP packet is an ARP request or an ARP response (i.e., using the opcode field), 
        # then call handle_arp_response() or handle_arp_request() accordingly. 
        self.handle_arp_request(pkt, intf) if arp.op == ARPOP_REQUEST else self.handle_arp_response(pkt, intf)

    def handle_arp_response(self, pkt: bytes, intf: str) -> None:
        """Handle the ARP response"""
        pkt = ARP(pkt)
        # udpate ARP table with sender IP to sender MAC
        self._arp_table[pkt.psrc] = pkt.hwsrc
        # send all packets in queue whose next hop corresponds to the sender IP address in the response
        for pkt1, next_hop1, intf1 in self.pending:
            if next_hop1 == pkt.psrc and intf1 == intf:
                eth = Ether(src=self.int_to_info[intf1].mac_addr, dst=self._arp_table[next_hop1], type=ETH_P_IP)
                frame = eth / pkt1
                self.send_frame(bytes(frame), intf1)
                self.pending.remove((pkt1, next_hop1, intf1))

    def handle_arp_request(self, pkt: bytes, intf: str) -> None:
        """Update ARP table and send response if IP destination matches with intf IP."""
        pkt = ARP(pkt)
        # if the target IP matches the IP of `intf`, then build and send an Ethernet frame containing the ARP response
        if pkt.pdst == self.int_to_info[intf].ipv4_addrs[0]:
            # udpate ARP table with sender IP to sender MAC
            self._arp_table[pkt.psrc] = pkt.hwsrc
            
            intf_mac_address = self.int_to_info[intf].mac_addr
            eth = Ether(src=intf_mac_address, dst=pkt.hwsrc, type=ETH_P_ARP)
            arp=ARP(
                op=ARPOP_REPLY,
                hwsrc=intf_mac_address,
                psrc=pkt.pdst,
                hwdst=pkt.hwsrc,
                pdst=pkt.psrc,
            )
            frame = eth / arp
            self.send_frame(bytes(frame), intf) 

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

        # check the host-wide ARP table to see if a mapping already exists
        if (dmac := self._arp_table.get(next_hop)):
            # if host-wide ARP table has mapping, then build the ethernet frame and send it
            eth = Ether(src=src_mac_addr, dst=dmac, type=ETH_P_IP)
            frame = eth / pkt
            self.send_frame(bytes(frame), intf)
        else:
            # if no mapping exists, queue the packet for later sending, create ARP request, then build and send ethernet frame
            self.pending.append((pkt, intf, next_hop)) # will send the IP packet later
            eth = Ether(src=src_mac_addr, dst="ff:ff:ff:ff:ff:ff", type=ETH_P_ARP)
            arp=ARP(
                op=ARPOP_REQUEST,
                hwsrc=src_mac_addr,
                psrc=self.int_to_info[intf].ipv4_addrs[0],
                hwdst="00:00:00:00:00:00",
                pdst=next_hop,
            )
            frame = eth / arp
            self.send_frame(bytes(frame), intf)
            self.pending.append((pkt, next_hop, intf))

    def send_packet(self, pkt: bytes) -> None:
        """
        Determine the the interface and next_hop from the destination
        ip of the packet.

        Args:
            pkt: an IPv4 packet
        """
        print(f'Attempting to send packet:\n{repr(pkt)}')
        ip = IP(pkt)
        intf, next_hop = self.forwarding_table.get_entry(ip.dst)
        if next_hop is None:
            # the case for subnets to when the host is directly connected
            next_hop = ip.dst
        if intf is None:
            # there is no matching route, so it should be dropped
            # and an ICMP "network unreachable" will be returned.
            return
        self.send_packet_on_int(pkt, intf, next_hop)



    def forward_packet(self, pkt: bytes) -> None:
        """
        Decrease the TTL and send the send the packet if it is not expired

        Args:
            pkt: the IP packet received
        """
        ip = IP(pkt)
        ip.ttl -= 1
        if ip.ttl <= 0:
            # expired packets should not be forwarded
            return
        self.send_packet(bytes(pkt))

    def not_my_frame(self, frame: bytes, intf: str) -> None:
        pass

    def not_my_packet(self, pkt: bytes, intf: str) -> None:
        """
        Determine what to do with packet if its unrecognized

        Args:
            pkt: the IP packet received
            intf: the interface on which it was received
        """
        if self._ip_forward:
            self.forward_packet(pkt)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--router', '-r',
            action='store_const', const=True, default=False,
            help='Act as a router by forwarding IP packets')
    args = parser.parse_args(sys.argv[1:])

    Host(args.router).run()

if __name__ == '__main__':
    main()
