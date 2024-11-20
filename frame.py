class Frame:
    DELIMITER: str = "|" # separator between other frames if sent as a single string

    def __init__(self, src_network: int, src_node: int, dest_network: int, dest_node: int, crc: int = 0, ack: int = 9999, ack_type: str | None = None, data: str = "") -> None:
        """
        src_network: source network id
        src_node: source node id
        dest_network: destination network id
        dest_node: destination node id
        crc: checksum of the data
        ack: if size of data is 0, then it's an ACK frame, otherwise it's sending data and should be set to the size of data
        ack_type: 
            - 00 no response time out , send again
            - 01 CRC error, send again
            - 10 firewalled, no need to send
            - 11 positive ACK
        data: data to be sent
        """
        self.src_network: int = src_network
        self.src_node: int = src_node
        self.dest_network: int = dest_network
        self.dest_node: int = dest_node
        # crc should contain the sum of the byte values truncated to 1 byte 
        if not data:
            self.crc: int = sum(bytearray(data.encode())) % 256
        else:
            self.crc: int = crc
        # if ack is not provided, it's the size of the data in bytes
        self.ack: int = ack if ack != 0 else len(data)
        self.ack_type: str | None = ack_type
        self.data: str = data
    
    def is_ack(self) -> bool:
        return self.ack == 0
    
    def to_bytes(self) -> bytes:
        """Convert frame fields to bytes for transmission."""
        src = self.network_node_to_number(self.src_network, self.src_node)
        dest = self.network_node_to_number(self.dest_network, self.dest_node)
        frame = f"{src},{dest},{self.crc},{int(self.ack)},{self.ack_type},{self.data}{self.DELIMITER}"
        return frame.encode()

    @classmethod
    def from_bytes(cls, frame_data: bytes) -> "Frame":
        """Create a Frame object from bytes received over the network."""
        frame_str = frame_data.decode()
        src, dest, crc, ack, ack_type, data = frame_str.split(",", 5)
        src_network, src_node = cls.number_to_network_node(int(src))
        dest_network, dest_node = cls.number_to_network_node(int(dest))
        ack = int(ack)
        data = data.rstrip(cls.DELIMITER)  # Remove the trailing delimiter
        return cls(src_network, src_node, dest_network, dest_node, int(crc), ack, ack_type, data)
    
    @staticmethod
    def network_node_to_number(network, node):
        """Convert a network and node to a number from 1-255."""
        if 1 <= network <= 16 and 1 <= node <= 16:
            return (network - 1) * 16 + node
        else:
            raise ValueError("network and node must be between 1 and 16 inclusive.")
    
    @staticmethod
    def number_to_network_node(num):
        """Convert a number from 1-255 to a network and node."""
        num = int(num)  # Ensure num is an integer
        network = (num - 1) // 16 + 1
        node = num - (network - 1) * 16
        return network, node