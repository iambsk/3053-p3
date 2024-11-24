import time
import select
import socket
import pickle
import traceback
import threading
from frame import Frame

BUFFER_SIZE = 1024

class Switch:
	def __init__(self, id: int, port: int = 8000, backbone_socket=None):
		self.id = id
		self.port = port
		self.switch_table = {}	# Maps node id to (address, socket)
		self.backbone_socket = backbone_socket	
		self.frame_buffers = {}
		self.firewall_rules = {}
		self.lock = threading.RLock()

		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server_socket.settimeout(2)  # give a timeout because it might block forever
		self.server_socket.bind(('localhost', self.port))
		self.server_socket.listen(5)
		print(f"Switch listening on port {self.port}")
	
	def start(self):
		threading.Thread(target=self.accept_connections).start()
		if self.backbone_socket:
			self.get_firewall_rules_from_backbone()
			threading.Thread(target=self.handle_backbone).start()

	def get_firewall_rules_from_backbone(self):
		try:
			# Receive the size of the firewall data first
			size_data = self.backbone_socket.recv(8)
			size = int.from_bytes(size_data, byteorder='big')
			
			# Now receive the actual firewall data based on the size
			firewall_data = b''
			while len(firewall_data) < size:
				packet = self.backbone_socket.recv(BUFFER_SIZE)
				if not packet:
					break
				firewall_data += packet
			
			self.firewall_rules = pickle.loads(firewall_data)
			print(f"Firewall rules: {self.firewall_rules}")
			print("Firewall rules received from backbone.")
		except Exception as e:
			print(f"Error receiving firewall rules from backbone: {e}")
	
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
								print(f"Received frame from backbone to Node {frame.dest}")
								self.forward_frame(frame, ['localhost', 9999])	# None since it's from backbone
							buffer = remaining
			except Exception as e:
				traceback.print_exc()
				print(f"Error receiving from backbone: {e}")
				break

	def accept_connections(self):
		while True:
			try:
				client_socket, addr = self.server_socket.accept()
				print(f"Accepted connection from {addr} on switch port {self.port}")
				threading.Thread(target=self.handle_node, args=(client_socket, addr)).start()
			except Exception as e: # could get the correct exception but this is good enough
				if "timed out" in str(e):
					pass
				else:
					print(f"Error accepting connection: {e}")

	def handle_node(self, client_socket, addr):
		# add the node to the switch table before starting the communication so that other threads can use it even if its just temporary
		with self.lock:
			self.switch_table[addr[1]] = (addr, client_socket)
		# print(f"Node connected from {addr}. Starting communication.")
		# Handle node communication
		while True:
			try:
				frame_bytes = client_socket.recv(BUFFER_SIZE)
				if not frame_bytes:
					print(f"Connection closed by Node {addr}.")
					# clean up the buffer since they disconnected
					with self.lock:
						if addr[1] in self.frame_buffers:
							del self.frame_buffers[addr[1]]
					break
				
				# add all the new frames to the buffer
				with self.lock:
					if addr[1] not in self.frame_buffers:
						self.frame_buffers[addr[1]] = b''
					# add to the frame buffer for a specific address
					self.frame_buffers[addr[1]] += frame_bytes
					buffer = self.frame_buffers[addr[1]]
					while Frame.DELIMITER.encode() in buffer:
						# Split the buffer at the first delimiter
						# frame_data is the first frame
						# remaining is the rest of the buffer
						frame_data, remaining = buffer.split(Frame.DELIMITER.encode(), 1)
						if frame_data:	
							frame = Frame.from_bytes(frame_data)
							# print(f"Received frame from Node {frame.src} to Node {frame.dest}.")
							if frame.src_network == self.id:
								if frame.src_node not in self.switch_table:
									if addr[1] in self.switch_table:
										del self.switch_table[addr[1]]
								self.switch_table[frame.src_node] = (addr, client_socket)
								# print(f"Node {frame.src} added to switch table.")
							print(f"Firewall rules: {self.firewall_rules}")
							# Check firewall rules before forwarding
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
								client_socket.sendall(nack_frame.to_bytes())
							else:
								self.forward_frame(frame, addr)
						buffer = remaining
					self.frame_buffers[addr[1]] = buffer

			except Exception as e:
				print(f"Error in handle_node: {e}")
				traceback.print_exc()
				# Clean up buffer on error
				with self.lock:
					if addr[1] in self.frame_buffers:
						del self.frame_buffers[addr[1]]
				break
	def forward_frame(self, frame, addr):
		print(f"Forwarding frame from Node {frame.src_network}_{frame.src_node} to Node {frame.dest_network}_{frame.dest_node}")
		with self.lock:
			# print("Inside the lock")
			# if frame.is_ack():
	   
				# return
			
			if frame.dest_network == self.id and frame.dest_node in self.switch_table:
				try:
					self.switch_table[frame.dest_node][1].sendall(frame.to_bytes())
					print(f"Successfully forwarded frame to Node {frame.dest_network}_{frame.dest_node}")
				except (ConnectionResetError, BrokenPipeError) as e: 
					print(f"Error forwarding to Node {frame.dest_network}_{frame.dest_node}: {e}")
					del self.switch_table[frame.dest_node]	# Remove if disconnected
					print(f"Node {frame.dest_network}_{frame.dest_node} removed from switch table due to disconnection.")
			elif frame.dest_network == self.id: 
				# broadcast the frame to all other nodes except the sender
				print(f"Broadcasting frame from Node {frame.src_network}_{frame.src_node} to all other nodes except Node with port {addr[1]}")
				
				
				
				# Then broadcast to local nodes
				for id, (node_addr, sock) in self.switch_table.items():
					if node_addr != addr:
						try:
							sock.sendall(frame.to_bytes())
							print(f"Broadcasted frame to Node {node_addr}")
						except (ConnectionResetError, BrokenPipeError) as e:
							print(f"Broadcast error from Node {frame.src_network}_{frame.src_node}: {e}")
							del self.switch_table[id]  # remove disconnected node
							print(f"Node {id} removed from switch table due to disconnection.")
			else:
				# Send to backbone switch since its not local
				try:
					self.backbone_socket.sendall(frame.to_bytes())
					print(f"Sent frame to backbone switch")
				except (ConnectionResetError, BrokenPipeError) as e:
					print(f"Error sending to backbone switch: {e}")


