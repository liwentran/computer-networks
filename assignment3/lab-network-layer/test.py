import unittest
from host import EthernetHeader, ARPPacket, ARPOP_REQUEST
from cougarnet.util import \
        mac_str_to_binary, mac_binary_to_str, \
        ip_str_to_binary, ip_binary_to_str

class TestEthernetHeader(unittest.TestCase):
    def test_create_header_to_bytes(self):
        hdr = EthernetHeader("01:23:45:67:89:AB", "CD:EF:12:34:56:78", 0x0800)
        
        self.assertEqual(hdr.to_bytes(), b'\x01\x23\x45\x67\x89\xab\xcd\xef\x12\x34\x56\x78\x08\x00')

    def test_bytes_to_header(self):
        hdr = EthernetHeader.from_bytes(b'\x01\x23\x45\x67\x89\xab\xcd\xef\x12\x34\x56\x78\x08\x00')
        self.assertEqual(hdr.dmac, "01:23:45:67:89:AB".lower())
        self.assertEqual(hdr.smac, "CD:EF:12:34:56:78".lower())
        self.assertEqual(hdr.ether_type, 0x0800)

    def test_create_arp_packet(self):
        pkt = ARPPacket(
            operation_code=ARPOP_REQUEST,
            src_hw_addr=mac_str_to_binary("01:23:45:67:89:AB"),
            src_protocol_addr=ip_str_to_binary("10.0.0.1"),
            dest_hw_addr=mac_str_to_binary("CD:EF:12:34:56:78"),
            dest_protocol_addr=ip_str_to_binary("10.0.0.2"),
        )
        self.assertEqual(pkt.to_bytes(), b'\x00\x01\x08\x00\x06\x04\x00\x01\x01#Eg\x89\xab\n\x00\x00\x01\xcd\xef\x124Vx\n\x00\x00\x02'
)

    def test_bytes_to_harp_packet(self):
        pkt = ARPPacket.from_bytes(b'\x00\x01\x08\x00\x06\x04\x00\x01\x01#Eg\x89\xab\n\x00\x00\x01\xcd\xef\x124Vx\n\x00\x00\x02')
        self.assertEqual(pkt.hw_type, 0x0001)
        self.assertEqual(pkt.protocol_type, 0x0800)
        self.assertEqual(pkt.hw_length, 6)
        self.assertEqual(pkt.protocol_length, 4)
        self.assertEqual(pkt.operation_code, 1)
        self.assertEqual(mac_binary_to_str(pkt.src_hw_addr), mac_binary_to_str(b'\x01\x23\x45\x67\x89\xab'))
        self.assertEqual(ip_binary_to_str(pkt.src_protocol_addr), ip_binary_to_str(b'\x0a\x00\x00\x01'))
        self.assertEqual(mac_binary_to_str(pkt.dest_hw_addr), mac_binary_to_str(b'\xcd\xef\x12\x34\x56\x78'))
        self.assertEqual(ip_binary_to_str(pkt.dest_protocol_addr), ip_binary_to_str(b'\x0a\x00\x00\x02'))

if __name__ == '__main__':
        unittest.main()