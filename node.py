import time
import random
import string
import socket
import threading
from frame import Frame

class Node:
    def __init__(self, node_id, switch_host, switch_port):
        self.node_id = node_id
        self.switch_host = switch_host
        self.switch_port = switch_port
        self.input_file = f"node{node_id}.txt"
        self.output_file = f"node{node_id}_output.txt"
        self.socket = None
        self.lock = threading.Lock()

    def connect_to_switch(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.switch_host, self.switch_port))
            print(f"Node {self.node_id} connected to switch.")
        except Exception as e:
            print(f"Error connecting to switch: {e}")

    def send_data(self, dest_id, data):
        frame = Frame(src=self.node_id, dest=dest_id, data=data)
        with self.lock:
            # 5% chance of sending erroneous data
            if random.random() <= 0.05:
                # make a corrupted frame
                frame.ack_type = "111"
                frame.ack = 299

            
            self.socket.sendall(frame.to_bytes())
            print(f"Node {self.node_id} sent data to Node {dest_id}: {frame.data}")
            
            # Wait for ACK with timeout
            ack_received = False
            start_time = time.time()
            timeout = 5  # 5 second timeout
            
            while not ack_received and (time.time() - start_time) < timeout:
                try:
                    ack_data = self.socket.recv(1024)
                    if ack_data:
                        ack_frame = Frame.from_bytes(ack_data)
                        if ack_frame.is_ack() and ack_frame.src == dest_id:
                            if ack_frame.ack_type == "00":
                                print(f"Node {self.node_id} received timeout ACK from Node {dest_id}, resending...")
                                # Resend the frame
                                self.socket.sendall(frame.to_bytes())
                            elif ack_frame.ack_type == "01":
                                print(f"Node {self.node_id} received CRC error ACK from Node {dest_id}, resending...")
                                # Resend the frame
                                self.socket.sendall(frame.to_bytes()) 
                            elif ack_frame.ack_type == "10":
                                print(f"Node {self.node_id} received firewall block ACK from Node {dest_id}")
                                ack_received = True # No need to retry
                            elif ack_frame.ack_type == "11":
                                print(f"Node {self.node_id} received positive ACK from Node {dest_id}")
                                ack_received = True
                except socket.timeout:
                    continue
                    
            if not ack_received:
                print(f"No ACK received from Node {dest_id} after {timeout} seconds")
                # Could implement retransmission here if needed
    def receive_data(self):
        buffer = ""
        while True:
            print(buffer)
            try:
                frame_data = self.socket.recv(1024)
                if not frame_data:
                    print(f"Node {self.node_id} connection closed.")
                    break
                buffer += frame_data.decode()
                while Frame.DELIMITER in buffer:
                    # Split buffer to process each frame
                    frame_str, buffer = buffer.split(Frame.DELIMITER, 1)
                    frame = Frame.from_bytes(frame_str.encode())
                    if frame.dest == self.node_id:
                        if frame.is_ack():
                            print(f"Node {self.node_id} received ACK from Node {frame.src}")
                        else:
                            self.write_output(frame.src, frame.data)
                            # 5% chance of not sending ACK
                            if random.random() <= 0.05:
                                print(f"Node {self.node_id} randomly failed to ACK message from Node {frame.src}")
                            else:
                                # Send ACK back to source
                                ack_frame = Frame(src=self.node_id, dest=frame.src, crc=0, ack=0, ack_type="11")
                                with self.lock:
                                    self.socket.sendall(ack_frame.to_bytes())
            except Exception as e:
                print(f"Error receiving data for Node {self.node_id}: {e}")
                break
            
    def read_input_and_send(self):
        with open(self.input_file, 'r') as file:
            for line in file:
                if line.strip():    
                    dest_id, data = line.strip().split(': ')
                    self.send_data(int(dest_id), data)

    def write_output(self, src_id, data):
        with open(self.output_file, 'a') as file:
            file.write(f"{src_id}: {data}\n")
        print(f"Node {self.node_id} received data from Node {src_id}: {data}")
