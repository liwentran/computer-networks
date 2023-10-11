"""TCP Send and Receive Buffer"""
class TCPSendBuffer(object):
    """
    A buffer that tracks all the bytes that need to be sent, and 
    which of those bytes have been sent but not acknolwedged.

    Attr:
        base_seq : int
            the sequence number of the first unacknolwedged byte in the window
        next_seq : int
            the sequence number of the first yet-to-be sent byte in the window
        last_seq : int
            the sequence number of the byte after the last byte in the buffer
    """
    def __init__(self, seq: int):
        self.buffer = b''
        self.base_seq = seq
        self.next_seq = self.base_seq
        self.last_seq = self.base_seq

    def bytes_not_yet_sent(self) -> int:
        """The number of bytes not-yet-sent in the buffer."""
        return self.last_seq - self.next_seq

    def bytes_outstanding(self) -> int:
        """The number of bytes sent but not yet acknowledged."""
        return self.next_seq - self.base_seq

    def put(self, data: bytes) -> int:
        """
        Add data to the buffer.

        Args:
            data : bytes
                raw bytes to be sent across a TCP connection
        """
        self.buffer += data
        self.last_seq += len(data)
        return self.last_seq

    def get(self, size: int) -> tuple[bytes, int]:
        """
        Retrieve (at most) the next size bytes of data that have not been sent. 
        
        Args:
            size : int
                the number of bytes, at most, to be retrieved from the buffer
                typically, size is max segment size (MSS)
                if size exceeds amount of data in the buffer, then only remaining bytes are sent

        Returns:
            A tuple of (bytes, int), where the first element is the bytes themselves and 
            the second is the starting seqeunce number.
        """
        idx_next_seq = self.next_seq-self.base_seq
        # if size exceeds amount of data in the buffer, return remaining
        if idx_next_seq + size > len(self.buffer):
            size = len(self.buffer) - idx_next_seq
        data = self.buffer[idx_next_seq:idx_next_seq + size]
        starting_seq = self.next_seq

        # shift next_seq
        self.next_seq += size

        return (data, starting_seq)

    def get_for_resend(self, size: int) -> tuple[bytes, int]:
        """
        Retrieve the next size bytes of data that have previously been sent
        but not yet acknowledged.  

        Args:
            size : int
                the number of bytes, at most, to be retrieved from the buffer
                typically, size is max segment size (MSS)
                if size exceeds amount of data in the buffer, then only remaining bytes are sent

        Returns:
            A tuple of (bytes, int), where the first element is the bytes themselves and 
            the second is the starting seqeunce number.
        """
        return (self.buffer[:size], self.base_seq)

    def slide(self, sequence: int) -> None:
        """
        Acknowledges bytes from the buffer that have previously been sent but not acknowledged.
        Updates base_seq to the sequence provided and changes the buffer to start there.

        Args:  
            sequence : int
                the sequence number returned in the ACK field of a TCP packet.
        """
        # Remove sent+acknolwedged bytes from buffer
        
        self.buffer = self.buffer[sequence-self.base_seq:]
        self.base_seq = sequence



class TCPReceiveBuffer(object):
    def __init__(self, seq: int):
        self.buffer = {}
        self.base_seq = seq

    def put(self, data: bytes, sequence: int) -> None:
        """
        Add data to the buffer. Maps the incoming segment of data by sequence number.

        Args:
            `data` : bytes
                the raw bytes that have been received in a TCP
            `sequence`: int
                the sequence number associated with the first byte of the data
        """
        # ignore old data
        if sequence + len(data) <= self.base_seq:
            return
        
        # ignore partial old data
        if sequence < self.base_seq:
            data = data[self.base_seq-sequence:]
            sequence = self.base_seq

        # if sequence already exists 
        if (segment := self.buffer.get(sequence)):
            # keep only the longest segment
            self.buffer[sequence] = segment if len(segment) > len(data) else data
        else:
            # insert data into buffer
            self.buffer[sequence] = data

        # trim overlaps
        prev_seq_end = -1
        for cur_seq_start in sorted(self.buffer.keys()):
            if cur_seq_start < prev_seq_end:
                # when overlap, trim the beginning of the segment
                overlapping_segment = self.buffer.pop(cur_seq_start)
                trimmed_segment = overlapping_segment[prev_seq_end-cur_seq_start:]

                # add trimmed segment
                if existing_segment := self.buffer.get(prev_seq_end): 
                    # if there already exist a segment at the new sequence start, keep the longer one, and don't update `prev_seq_end`
                    self.buffer[prev_seq_end] = existing_segment if len(existing_segment) > len(trimmed_segment) else trimmed_segment
                else:
                    # insert trimmed segment at the new sequence start and update `prev_seq_end`
                    self.buffer[prev_seq_end] = trimmed_segment
                    prev_seq_end = prev_seq_end + len(trimmed_segment)
            else:
                # no overlap, just update `prev_seq_end`
                prev_seq_end = cur_seq_start + len(self.buffer[cur_seq_start])
                


    def get(self) -> tuple[bytes, int]:
        """
        Retrieves the largest set of contiguous (with no "holes") bytes
        that have been received, starting with `base_seq`, eliminating any duplicates.
        Updates `base_seq` to the sequence number of the next segment expected.
    
        Returns:
            A tuple of `(bytes, int)` where the first element is the data and the second 
            is the sequence number of the starting sequence of bytes.
        """
        initial_base_seq = self.base_seq
        prev_seq_end = self.base_seq
        data = b''
        # iterate the segments in sequence order
        for cur_seq_start in sorted(self.buffer.keys()):
            if prev_seq_end == cur_seq_start:
                # add contiguous data and remove from buffer
                data += self.buffer.pop(cur_seq_start)
                prev_seq_end = self.base_seq + len(data)
            else:
                # there is a hole
                break

        # update base_seq
        self.base_seq = prev_seq_end
        return (data, initial_base_seq)
