import time
import select
import socket
import traceback
import threading
from hub import Hub
from frame import Frame

BUFFER_SIZE = 1024

class BackboneHub(Hub):
    def __init__(self, port: int = 8001, global_switch_table: dict[int, int] = {}, switch_table: dict[int, tuple[any, socket.socket]] = {}):
        self.port = port
        self.frame_buffers = {}
        # switch table is a dictionary that maps the destination port to the address and socket
        self.switch_table: dict[int, tuple[any, socket.socket]] = switch_table
        # contains every node and the switch it's connected to, key is node id, value is switch id
        self.global_switch_table: dict[int, int] = global_switch_table
        self.lock = threading.RLock()
        self.switches = []  # switches connected
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        print(f"Switch listening on port {self.port}")
        
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
                        
                        # Check global switch table for destination node's switch
                        if frame.dest in self.global_switch_table:
                            dest_switch_id = self.global_switch_table[frame.dest]
                            socket = self.switch_table[dest_switch_id][1]
                            try:
                                if socket != switch_socket:  # Don't send back to source
                                    socket.sendall(frame.to_bytes())
                                    print(f"Forwarded frame to switch for node {frame.dest}")
                            except (ConnectionResetError, BrokenPipeError) as e:
                                print(f"Error forwarding to switch: {e}")
                                if socket in self.switches:
                                    self.switches.remove(socket)
                        else:
                            print(f"No switch found for destination node {frame.dest}")
                            
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