import time
import random
import string
import socket
import threading
from frame import Frame

class Node:
    def __init__(self, id, switch_host, switch_port, network_id):
        self.id = id
        self.switch_host = switch_host
        self.switch_port = switch_port
        self.network_id = network_id
        self.input_file = f"node{network_id}_{id}.txt"
        self.output_file = f"node{network_id}_{id}_output.txt"
        self.socket = None
        self.lock = threading.Lock()

    def connect_to_switch(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.switch_host, self.switch_port))
            print(f"Node {self.id} connected to switch.")
        except Exception as e:
            print(f"Error connecting to switch: {e}")

    def send_data(self, dest_network, dest_node, data):
    
        frame = Frame(src_network=self.network_id, src_node=self.id, dest_network=dest_network, dest_node=dest_node, data=data)
        with self.lock:
            # 5% chance of sending erroneous data
            if random.random() <= 0.05:
                # make a corrupted frame
                frame.ack_type = "111"
                frame.ack = 299

            
            self.socket.sendall(frame.to_bytes())
            print(f"Node {self.id} sent data to Node {dest_network}_{dest_node}: {frame.data}")
            
            # Wait for ACK with timeout
        ack_received = False
        start_time = time.time()
        timeout = 20  # 5 second timeout
            
        while not ack_received and (time.time() - start_time) < timeout:
            try:
                ack_data = self.socket.recv(1024)
                print(f"Node {self.id} received ACK data: {ack_data}")
                if ack_data:
                    with self.lock:
                        ack_frame = Frame.from_bytes(ack_data)
                        if ack_frame.is_ack() and ack_frame.src_network == dest_network and ack_frame.src_node == dest_node:
                            if ack_frame.ack_type == "00":
                                print(f"Node {self.id} received timeout ACK from Node {dest_network}_{dest_node}, resending...")
                                # Resend the frame
                                self.socket.sendall(frame.to_bytes())
                            elif ack_frame.ack_type == "01":
                                print(f"Node {self.id} received CRC error ACK from Node {dest_network}_{dest_node}, resending...")
                                # Resend the frame
                                self.socket.sendall(frame.to_bytes()) 
                            elif ack_frame.ack_type == "10":
                                print(f"Node {self.id} received firewall block ACK from Node {dest_network}_{dest_node}")
                                ack_received = True # No need to retry
                            elif ack_frame.ack_type == "11":
                                print(f"Node {self.id} received positive ACK from Node {dest_network}_{dest_node}")
                                ack_received = True
            except socket.timeout:
                print(f"Node {self.id} received timeout ACK from Node {dest_network}_{dest_node}, resending...")
                # Resend the frame
                self.socket.sendall(frame.to_bytes())
                continue
                    
            if not ack_received:
                print(f"No ACK received from Node {dest_network}_{dest_node} after {timeout} seconds")
                # Could implement retransmission here if needed
    def receive_data(self):
        print(f"Node {self.network_id}_{self.id} receiving data")
        buffer = b""
        while True:
            print(buffer)
            try:
                frame_data = self.socket.recv(1024)
                if not frame_data:
                    print(f"Node {self.network_id}_{self.id} connection closed.")
                    break
                buffer += frame_data
                # Process each frame in the buffer
                while Frame.DELIMITER.encode() in buffer:
                    frame_str, buffer = buffer.split(Frame.DELIMITER.encode(), 1)
                    frame = Frame.from_bytes(frame_str)
                    if frame.dest_network == self.network_id and frame.dest_node == self.id:
                        if frame.is_ack():
                            print(f"Node {self.network_id}_{self.id} received ACK from Node {frame.src_network}_{frame.src_node}")
                        else:
                            self.write_output(frame.src_network, frame.src_node, frame.data)
                            # 5% chance of not sending ACK
                            if random.random() <= 0.05:
                                print(f"Node {self.network_id}_{self.id} randomly failed to ACK message from Node {frame.src_network}_{frame.src_node}")
                                ack_frame = Frame(src_network=self.network_id, src_node=self.id, dest_network=frame.src_network, dest_node=frame.src_node, ack=0, ack_type="00")
                                with self.lock:
                                    self.socket.sendall(ack_frame.to_bytes())
                            else:
                                print(f"Node {self.network_id}_{self.id} sending ACK to Node {frame.src_network}_{frame.src_node}")
                                # Send ACK back to source
                                ack_frame = Frame(src_network=self.network_id, src_node=self.id, dest_network=frame.src_network, dest_node=frame.src_node, ack=0, ack_type="11")
                                with self.lock:
                                    self.socket.sendall(ack_frame.to_bytes())
            except Exception as e:
                print(f"Error receiving data for Node {self.network_id}_{self.id}: {e}")
                break
            
    def read_input_and_send(self):
        print(f"Node {self.network_id}_{self.id} reading input file: {self.input_file}")
        with open(self.input_file, 'r') as file:
            for line in file:
                if line.strip():
                    print(f"Node {self.network_id}_{self.id} read line: {line.strip()}")    
                    dest_id, data = line.strip().split(': ')
                    dest_network, dest_node = map(int, dest_id.split('_'))
                    print(f"Node {self.network_id}_{self.id} sending data to Node {dest_network}_{dest_node}: {data}")
                    self.send_data(dest_network, dest_node, data)
                    
    def write_output(self, src_network, src_node, data):
        with open(self.output_file, 'a') as file:
            file.write(f"{src_network}_{src_node}: {data}\n")
        print(f"Node {self.id} received data from Node {src_network}_{src_node}: {data}")
