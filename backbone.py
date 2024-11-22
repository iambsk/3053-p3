import time
import select
import socket
import traceback
import threading
from switch import Switch
from frame import Frame

BUFFER_SIZE = 1024

class BackboneSwitch(Switch):
    def __init__(self, port: int = 8001, global_switch_table: dict[int, int] = {}, 
                 switch_table: dict[int, tuple[any, socket.socket]] = {}, 
                 firewall_rules: dict[str, str] = None):
        self.port = port
        self.frame_buffers = {}
        # switch table is a dictionary that maps the switch id to the address and socket
        self.switch_table: dict[int, tuple[any, socket.socket]] = switch_table
        # contains every node and the switch it's connected to, key is node id, value is switch id
        self.global_switch_table: dict[int, int] = global_switch_table
        self.lock = threading.RLock()
        self.switches = []  # switches connected
        self.firewall_rules = firewall_rules or {}  # firewall rules: {"1_1_2_2": "Block", "1_2_2_1": "Allow"}
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        print(f"Switch listening on port {self.port}")
        
    def start(self):
        threading.Thread(target=self.accept_connections).start()
    
    def accept_connections(self):
        while True:
            switch_socket, addr = self.server_socket.accept()
            self.switches.append(switch_socket)
            threading.Thread(target=self.handle_switch, args=(switch_socket, addr)).start()

    def handle_switch(self, switch_socket, addr):
        while True:
            try:
                frame_bytes = switch_socket.recv(BUFFER_SIZE)
                if not frame_bytes:
                    print(f"Connection closed by switch at {addr}")
                    if addr[1] in self.frame_buffers:
                        del self.frame_buffers[addr[1]]
                    if switch_socket in self.switches:
                        self.switches.remove(switch_socket)
                    break

                if addr[1] not in self.frame_buffers:
                    self.frame_buffers[addr[1]] = b''
                self.frame_buffers[addr[1]] += frame_bytes
                buffer = self.frame_buffers[addr[1]]    
                while Frame.DELIMITER.encode() in buffer:
                    frame_data, remaining = buffer.split(Frame.DELIMITER.encode(), 1)
                    if frame_data:  
                        frame = Frame.from_bytes(frame_data)
                        print(f"Backbone received frame from switch at {addr}")

                        # Check if the traffic is allowed by firewall rules
                        rule_key = f"{frame.src_network}_{frame.src_node}_{frame.dest_network}_{frame.dest_node}"
                        if self.firewall_rules.get(rule_key, "Allow") == "Block":
                            print(f"Blocked traffic from {frame.src_network}_{frame.src_node} to {frame.dest_network}_{frame.dest_node}")
                            nack_frame = Frame(
                                src_network=frame.dest_network,
                                src_node=frame.dest_node,
                                dest_network=frame.src_network,
                                dest_node=frame.src_node,
                                ack=0,
                                ack_type="10"
                            )
                            switch_socket.sendall(nack_frame.to_bytes())
                        else:
                            # Check global switch table for destination node's switch
                            if frame.dest_network in self.switch_table:
                                dest_switch_id = frame.dest_network
                                socket = self.switch_table[dest_switch_id][1]
                                try:
                                    if socket != switch_socket:  # Don't send back to source
                                        socket.sendall(frame.to_bytes())
                                        print(f"Forwarded frame to switch for node {frame.dest_network}_{frame.dest_node}")
                                except (ConnectionResetError, BrokenPipeError) as e:
                                    print(f"Error forwarding to switch: {e}")
                                    if socket in self.switches:
                                        self.switches.remove(socket)
                            else:
                                print(f"No switch found for destination node {frame.dest_network}_{frame.dest_node}")
                            
                    buffer = remaining
                self.frame_buffers[addr[1]] = buffer

            except Exception as e:
                print(f"Error in handle_switch: {e}")
                traceback.print_exc()
                if addr[1] in self.frame_buffers:
                    del self.frame_buffers[addr[1]]
                if switch_socket in self.switches:
                    self.switches.remove(switch_socket)
                break
    
    def set_switch_table(self, switch_table: dict[int, tuple[any, socket.socket]]):
        self.switch_table = switch_table