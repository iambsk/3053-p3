class Frame:
    DELIMITER: str = "|" # separator between other frames if sent as a single string

    def __init__(self, src: int, dest: int, crc: int, ack: int, ack_type: str | None = None, data: str = "") -> None:
        """
        src: source node id
        dest: destination node id
        crc: checksum of the data
        ack: if size of data is 0, then it's an ACK frame, otherwise it's sending data and should be set to the size of data
        ack_type: 
            - 00 no response time out , send again
            - 01 CRC error, send again
            - 10 firewalled, no need to send
            - 11 positive ACK
        data: data to be sent
        """
        self.src: int = src
        self.dest: int = dest
        self.crc: int = crc
        self.ack: int = ack
        self.ack_type: str | None = ack_type
        self.data: str = data
    
    def is_ack(self) -> bool:
        return self.ack == 0
    
    def to_bytes(self) -> bytes:
        """Convert frame fields to bytes for transmission."""
        frame = f"{self.src},{self.dest},{self.crc},{int(self.ack)},{self.ack_type},{self.data}{self.DELIMITER}"
        return frame.encode()

    @classmethod
    def from_bytes(cls, frame_data: bytes) -> "Frame":
        """Create a Frame object from bytes received over the network."""
        frame_str = frame_data.decode()
        src, dest, crc, ack, ack_type, data = frame_str.split(",", 5)
        ack = bool(int(ack))
        data = data.rstrip(cls.DELIMITER)  # Remove the trailing delimiter
        return cls(int(src), int(dest), int(crc), ack, ack_type, data)