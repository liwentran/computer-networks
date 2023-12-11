#!/usr/bin/python3

import asyncio
from cougarnet.sim.host import BaseHost
import struct 
import os
import json

class Switch(BaseHost):
    def __init__(self):
        super().__init__()
        self._outgoing = {}  # MAC : intf
        self._remove_events = {} 
        self._vlans = {} 
        self._intfs = {}
        self._trunks = set() # of intf

        blob = os.environ.get('COUGARNET_VLAN', '')
        if blob:
            vlan_info = json.loads(blob)
            for myint in self.physical_interfaces:
                val = vlan_info[myint]
                if val == 'trunk':
                    # if intf is trunk, add it to the list of trunk interfaces
                    self._trunks.add(myint)
                else:
                    vlan_val = int(val[4:])
                    if vlan_val not in self._vlans:
                        # instantiate for this vlan_val
                        self._vlans[vlan_val] = []
                                                
                    self._vlans[vlan_val].append(myint)
                    self._intfs[myint] = vlan_val
        else:
            
            for myint in self.physical_interfaces:
                vlan_val = 1
                if vlan_val not in self._vlans:
                    self._vlans[vlan_val] = []
                
                # Code for the loop. Hint: it has to do with handling vlan_val and is only 2 lines of code.
                self._vlans[vlan_val].append(myint)
                self._intfs[myint] = vlan_val

        

    def _handle_frame(self, frame: bytes, intf: str) -> None:
        src = frame[6:12]
        dst = frame[:6]

        if intf in self._trunks:
            vlan = struct.unpack('!H', frame[14:16])[0]
            frame = frame[:12] + frame[16:]
        else:
            vlan = self._intfs[intf]

        if dst in self._outgoing:
            # we know where to send it
            if self._outgoing[dst] in self._trunks:
                # if the intf is in trunks, then its a 801.1Q frame. Convert to Ethernet frame. 
                frame = frame[:12] + frame[16:]

            self.send_frame(frame, self._outgoing[dst])
        else:
            # otherwise, broadcast this frame
            for myint in self.physical_interfaces:
                if intf != myint and \
                        (myint in self._trunks or self._intfs[myint] == vlan):
                    if myint in self._trunks:
                        # if the intf is in trunks, it must be a 801.1Q frame
                        fr = frame[:12] + b'\x81\x00' + struct.pack('!H', vlan) + frame[16:]
                    else:
                        fr = frame

                    self.send_frame(fr, myint)
            
        self._outgoing[src] = intf
        ev = self._remove_events.get(src, None)
        if ev is not None:
            ev.cancel()
        loop = asyncio.get_event_loop()

        # The aging time of a new table entry is 8 seconds.
        # When a frame arrives corresponding to an existing entry, its aging time is reset to 8 seconds.
        self._remove_events[src] = loop.call_later(8, self.del_outgoing, src)

    def del_outgoing(self, src):
        del self._outgoing[src]

def main():
    Switch().run()

if __name__ == '__main__':
    main()
