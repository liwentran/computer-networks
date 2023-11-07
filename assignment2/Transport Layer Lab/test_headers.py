import binascii
import unittest

from headers import IPv4Header, UDPHeader, TCPHeader, ICMPHeader

from mysocket import TCP_FLAGS_SYN, TCP_FLAGS_ACK, \
        IPPROTO_TCP, IPPROTO_UDP
    

class TestHeaders(unittest.TestCase):
    def test_ipv4_header(self):
        ip_hdr_bytes = b'E\x00\x02\x05\x00\x00\x00\x00\x80\x06\x00\x00\xc0\xa8\n\x14\xc0\xa8\x0f\x02'

        hdr = IPv4Header.from_bytes(ip_hdr_bytes)

        actual_value = (hdr.length, hdr.ttl, hdr.protocol,
                hdr.checksum, hdr.src, hdr.dst)
        correct_value = (517, 128, 6, 0, '192.168.10.20', '192.168.15.2')

        self.assertEqual(actual_value, correct_value)


        ip_hdr_obj = IPv4Header(1057, 64, 17, 0, '128.187.82.254', '128.170.51.63')


        actual_value = binascii.hexlify(ip_hdr_obj.to_bytes())
        correct_value = b'45000421000000004011000080bb52fe80aa333f'

        self.assertEqual(actual_value, correct_value)


    def test_udp_header(self):
        udp_hdr_bytes = b'\x04+\x1ej\x07\xe5\x00\x00'

        hdr = UDPHeader.from_bytes(udp_hdr_bytes)
        actual_value = (hdr.sport, hdr.dport, hdr.length, hdr.checksum)
        correct_value = (1067, 7786, 2021, 0)

        self.assertEqual(actual_value, correct_value)


        udp_hdr_obj = UDPHeader(1067, 7786, 2021, 0)

        actual_value = binascii.hexlify(udp_hdr_obj.to_bytes())
        correct_value = b'042b1e6a07e50000'

        self.assertEqual(actual_value, correct_value)


    def test_tcp_header(self):
        tcp_hdr_bytes = b'\xffC\xd5\xd3\x00\xa4DV\x00\x82\\,P\x10\x00@\x00\x00\x00\x00'

        hdr = TCPHeader.from_bytes(tcp_hdr_bytes)

        actual_value = (hdr.sport, hdr.dport, hdr.seq,
                hdr.ack, hdr.flags, hdr.checksum)
        correct_value = (65347, 54739, 10765398, 8543276, 16, 0)

        self.assertEqual(actual_value, correct_value)


        tcp_hdr_obj = TCPHeader(1123, 2025, 876539, 452850, TCP_FLAGS_SYN | TCP_FLAGS_ACK, 0)

        actual_value = binascii.hexlify(tcp_hdr_obj.to_bytes())
        correct_value = b'046307e9000d5ffb0006e8f25012004000000000'

        self.assertEqual(actual_value, correct_value)

    def test_icmp_header(self):
        icmp_header_bytes = b'\x15\x02\x00\x00\x00\x00\x00\x00'

        hdr = ICMPHeader.from_bytes(icmp_header_bytes)
        actual_value = (hdr.type, hdr.code, hdr.checksum)
        correct_value = (21, 2, 0)
        
        self.assertEqual(actual_value, correct_value)
        
        icmp_hdr_obj = ICMPHeader(5, 12, 0)

        actual_value = binascii.hexlify(icmp_hdr_obj.to_bytes())
        correct_value = b'050c000000000000'
        self.assertEqual(actual_value, correct_value)

if __name__ == '__main__':
    unittest.main()
