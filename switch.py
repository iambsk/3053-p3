import time
import select
import socket
import traceback
import threading
from frame import Frame

BUFFER_SIZE = 1024

class Switch:
    def __init__(self, id: int, port: int = 8000, backbone_socket=None, firewall_rules: dict[str, str] = None):
        self.id = id
        self.port = port
        self.switch_table = {}  # Maps node ID to (address, socket)
        self.backbone_socket = backbone_socket
        self.frame_buffers = {}
        self.lock = threading.RLock()
        self.firewall_rules = firewall_rules or {}  # Firewall rules: {"1_1_2_2": "Block"}

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        print(f"Switch listening on port {self.port}")

    def start(self):
        threading.Thread(target=self.accept_connections).start()
        if self.backbone_socket:
            threading.Thread(target=self.handle_backbone).start()

    def accept_connections(self):
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"Accepted connection from {addr} on switch port {self.port}")
                threading.Thread(target=self.handle_node, args=(client_socket, addr)).start()
            except Exception as e:
                if "timed out" not in str(e):
                    print(f"Error accepting connection: {e}")

    def handle_node(self, client_socket, addr):
        with self.lock:
            self.switch_table[addr[1]] = (addr, client_socket)

        while True:
            try:
                frame_bytes = client_socket.recv(BUFFER_SIZE)
                if not frame_bytes:
                    print(f"Connection closed by Node {addr}.")
                    with self.lock:
                        if addr[1] in self.frame_buffers:
                            del self.frame_buffers[addr[1]]
                    break

                if addr[1] not in self.frame_buffers:
                    self.frame_buffers[addr[1]] = b''
                self.frame_buffers[addr[1]] += frame_bytes
                buffer = self.frame_buffers[addr[1]]

                while Frame.DELIMITER.encode() in buffer:
                    frame_data, remaining = buffer.split(Frame.DELIMITER.encode(), 1)
                    if frame_data:
                        frame = Frame.from_bytes(frame_data)
                        print(f"Received frame from Node {frame.src_network}_{frame.src_node} to Node {frame.dest_network}_{frame.dest_node}")

                        # Check firewall rules
                        rule_key = f"{frame.src_network}_{frame.src_node}_{frame.dest_network}_{frame.dest_node}"
                        if self.firewall_rules.get(rule_key, "Allow") == "Block":
                            print(f"Blocked local traffic from {frame.src_network}_{frame.src_node} to {frame.dest_network}_{frame.dest_node}")
                            nack_frame = Frame(
                                src_network=frame.dest_network,
                                src_node=frame.dest_node,
                                dest_network=frame.src_network,
                                dest_node=frame.src_node,
                                ack=0,
                                ack_type="10"
                            )
                            client_socket.sendall(nack_frame.to_bytes())
                        else:
                            # Forward frame logic
                            if frame.dest_node in self.switch_table:
                                dest_socket = self.switch_table[frame.dest_node][1]
                                dest_socket.sendall(frame.to_bytes())
                            else:
                                # Send to backbone if global
                                if self.backbone_socket:
                                    self.backbone_socket.sendall(frame.to_bytes())

                    buffer = remaining
                self.frame_buffers[addr[1]] = buffer

            except Exception as e:
                print(f"Error in handle_node: {e}")
                traceback.print_exc()
                with self.lock:
                    if addr[1] in self.frame_buffers:
                        del self.frame_buffers[addr[1]]
                break

    def handle_backbone(self):
        while True:
            try:
                frame_bytes = self.backbone_socket.recv(BUFFER_SIZE)
                if frame_bytes:
                    with self.lock:
                        buffer = frame_bytes
                        while Frame.DELIMITER.encode() in buffer:
                            frame_data, remaining = buffer.split(Frame.DELIMITER.encode(), 1)
                            if frame_data:
                                frame = Frame.from_bytes(frame_data)
                                print(f"Received frame from backbone to Node {frame.dest_network}_{frame.dest_node}")
                                if frame.dest_node in self.switch_table:
                                    dest_socket = self.switch_table[frame.dest_node][1]
                                    dest_socket.sendall(frame.to_bytes())
                                buffer = remaining
            except Exception as e:
                traceback.print_exc()
                print(f"Error receiving from backbone: {e}")
                break

    def forward_frame(self, frame, addr):
        print(f"Forwarding frame from Node {frame.src_network}_{frame.src_node} to Node {frame.dest_network}_{frame.dest_node}")
        with self.lock:
            if frame.dest_network == self.id and frame.dest_node in self.switch_table:
                try:
                    self.switch_table[frame.dest_node][1].sendall(frame.to_bytes())
                    print(f"Successfully forwarded frame to Node {frame.dest_network}_{frame.dest_node}")
                except (ConnectionResetError, BrokenPipeError) as e:
                    print(f"Error forwarding to Node {frame.dest_network}_{frame.dest_node}: {e}")
                    del self.switch_table[frame.dest_node]
            else:
                if self.backbone_socket:
                    self.backbone_socket.sendall(frame.to_bytes())
