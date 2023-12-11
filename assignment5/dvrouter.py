#!/usr/bin/env python3

import asyncio
import json
import socket

NEIGHBOR_CHECK_INTERVAL = 3
DV_TABLE_SEND_INTERVAL = 1
DV_PORT = 5016

from cougarnet.sim.host import BaseHost

import prefix
from mysocket import UDPSocket
from transporthost import TransportHost

class DVRouter(TransportHost):
    def __init__(self):
        super().__init__(True)

        self.my_dv = {}
        self.neighbor_dvs = {}

        self._dv_socks = {}

        # Forwarding table is initialized in Host.__init__();
        # Host is an ancestor class that handles IP Forwarding

        self._initialize_dv_sock()
        self._link_down_alarm = {}
        self._neighbor_name_to_ip = {}

    def _initialize_dv_sock(self) -> None:
        '''Initialize the socket that will be used for sending and receiving DV
        communications to and from neighbors.
        '''

        for intf in self.physical_interfaces:
            sock = UDPSocket(
                    self.int_to_info[intf].ipv4_addrs[0],
                    DV_PORT,
                    self.send_packet, self._handle_msg)
            self._dv_socks[intf] = sock
            self.install_socket_udp(
                    self.int_to_info[intf].ipv4_addrs[0],
                    DV_PORT, sock)
            #XXX find a better way to accept packets
            self.install_socket_udp(
                    self.bcast_for_int(intf),
                    DV_PORT, sock)

    def init_dv(self):
        '''Set up our instance to work with the event loop, initialize our DV,
        and schedule our regular updates to be sent to neighbors.
        '''

        loop = asyncio.get_event_loop()

        # Schedule self.send_dv_next() to be called in 1 second and
        # self.update_dv_next() to be called in 0.5 seconds.
        loop.call_later(DV_TABLE_SEND_INTERVAL, self.send_dv_next)
        loop.call_later(DV_TABLE_SEND_INTERVAL - DV_TABLE_SEND_INTERVAL / 2,
                self.update_dv_next)

    def _handle_msg(self) -> None:
        ''' Receive and handle a message received on the UDP socket that is
        being used for DV messages.
        '''

        for intf in self._dv_socks:
            #XXX This check for non-zero buffer should go in recvfrom()
            if self._dv_socks[intf].buffer:
                data, addr, port = self._dv_socks[intf].recvfrom()
                self.handle_dv_message(data)

    def _send_msg(self, msg: bytes, dst: str) -> None:
        '''Send a DV message, msg, on our UDP socket to dst.'''

        #XXX We should probably use the correct socket in the future, but this
        # will work for now
        for intf in self._dv_socks:
            self._dv_socks[intf].sendto(msg, dst, DV_PORT)
            break

    def handle_dv_message(self, msg: bytes) -> None:
        """
        Does everything associated with receiving a DV message.
        
        Args:
            msg: a DV message consisting of a JSON representing the DB of the neighbor that sent it.
        """
        # extract the ip address, name, and DV of the neighboring node
        d = json.loads(msg.decode('utf-8'))
        neighbor_name = d.get('name')

        # discard packet if its own
        if neighbor_name == self.hostname:
            return

        # assign values to self._neighbor_name_to_ip and self.neighbor_dvs
        self._neighbor_name_to_ip[neighbor_name] = d.get('ip')
        self.neighbor_dvs[neighbor_name] = d.get('dv')

        if neighbor_name in self._link_down_alarm:
            # This is the second time you've seen this neighbor in a certain period of time
            # so cancel the down link detection function
            self._link_down_alarm[neighbor_name].cancel()

        loop = asyncio.get_event_loop()

        # Pessimistically believing that I will never see this neighbor again, start timer for down link alert
        self._link_down_alarm[neighbor_name] = loop.call_later(3, self.handle_down_link, neighbor_name)

    def send_dv_next(self):
        '''Send DV to neighbors, and schedule this method to be called again in
        1 second (DV_TABLE_SEND_INTERVAL).
        '''

        self.send_dv()
        loop = asyncio.get_event_loop()
        loop.call_later(DV_TABLE_SEND_INTERVAL, self.send_dv_next)

    def update_dv_next(self):
        '''Update DV using neighbors' DVs.  Then schedule this method to be
        called again in 1 second (DV_TABLE_SEND_INTERVAL).
        '''

        self.update_dv()
        loop = asyncio.get_event_loop()
        loop.call_later(DV_TABLE_SEND_INTERVAL, self.update_dv_next)

    def handle_down_link(self, neighbor: str):
        """
        Called whenever a router has detected a down link (through the lack of keep-alive DV messages).
        Discards the DV of the neighbor whose link is down.

        Args:
            neighbor: the hostname of the neighbor corresponding tot he link that is no longer up.
        """
        self.log(f'Link down: {neighbor}')
        del self.neighbor_dvs[neighbor]

    def resolve_neighbor_dvs(self):
        '''Return a copy of the mapping of neighbors to distance vectors, with
        IP addresses replaced by names in every neighbor DV.
        '''

        neighbor_dvs = {}
        for neighbor in self.neighbor_dvs:
            neighbor_dvs[neighbor] = self.resolve_dv(self.neighbor_dvs[neighbor])
        return neighbor_dvs

    def resolve_dv(self, dv: dict) -> dict:
        '''Return a copy of distance vector dv with IP addresses replaced by
        names.
        '''

        resolved_dv = {}
        for dst, distance in dv.items():
            if '/' not in dst:
                try:
                    dst = socket.getnameinfo((dst, 0), 0)[0]
                except:
                    pass
            resolved_dv[dst] = distance
        return resolved_dv

    def update_dv(self) -> None:
        """
        Implements the Bellman-Ford algorithm to create a new DV. In the case that the DV changes,
        the IP addresses of the neighbors with shortest distances to IP prefixes are used to create 
        new forwarding table entries. Called every second.
        """
        forwarding_table = {}

        # get neighboring costs (1 for the purposes of this lab)
        neighbor_costs = {neighbor : 1 for neighbor in self.neighbor_dvs.keys()}
        
        # initialize DV with distance 0 to its IP prefixes
        dv = dict([(prefix.ip_int_to_str(prefix.ip_prefix(prefix.ip_str_to_int(intinfo.ipv4_addrs[0]), socket.AF_INET, intinfo.ipv4_prefix_len), socket.AF_INET)+'/'+str(intinfo.ipv4_prefix_len), 0) \
                for intinfo in self.int_to_info.values() if intinfo.ipv4_addrs])        

        # bellman ford
        for neighbor_name, neighbor_dv in self.neighbor_dvs.items():
            neighbor_cost = neighbor_costs[neighbor_name]
            for y_name, y_cost in neighbor_dv.items():
                if y_name not in dv or dv[y_name] > neighbor_cost + y_cost:
                    dv[y_name] = neighbor_cost + y_cost
                    forwarding_table[y_name] = self._neighbor_name_to_ip.get(neighbor_name)

        # check if dv was updated
        send_new_dv = dv != self.my_dv

        # in the case that the DV changes, create new forwarding table entries
        self.my_dv = dv
        if send_new_dv:
            # update forwarding table
            self.forwarding_table.flush()
            for dst in forwarding_table:
                self.forwarding_table.add_entry(dst, None, forwarding_table[dst])


    def send_dv(self) -> None:
        """
        Sends its own DV to each of its neighbor. Called every second. 
        """
        print('Sending DV')
        for intf in self.physical_interfaces:
            d = { 'name': self.hostname,
                    'ip': self.int_to_info[intf].ipv4_addrs[0],
                    'dv': self.my_dv }
            d_json = json.dumps(d).encode('utf-8')
            bcast = self.bcast_for_int(intf)
            self._send_msg(d_json, bcast)

def main():
    router = DVRouter()
    router.init_dv()
    router.run()

if __name__ == '__main__':
    main()
