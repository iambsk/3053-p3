import time
import select
import socket
import traceback
import threading
import pickle
from switch import Switch
from frame import Frame

BUFFER_SIZE = 1024

class BackboneSwitch(Switch):
	def __init__(self, port: int, global_switch_table: dict[int, int] = {}, switch_table: dict[int, tuple[any, socket.socket]] = {}):
		self.stop_event = threading.Event()
		self.port = port
		self.frame_buffers = {}
		# switch table is a dictionary that maps the switch id to the address and socket
		self.switch_table: dict[int, tuple[any, socket.socket]] = switch_table
		# contains every node and the switch it's connected to, key is node id, value is switch id
		self.global_switch_table: dict[int, int] = global_switch_table
		self.lock = threading.RLock()
		self.switches = []	# switches connected
		
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server_socket.bind(('localhost', self.port))
		self.server_socket.listen(5)
		print(f"Switch listening on port {self.port}")
		
	def start(self):
		self.stop_event.clear()
		threading.Thread(target=self.accept_connections).start()
	
	def accept_connections(self):
		while not self.stop_event.is_set():
			switch_socket, addr = self.server_socket.accept()
			self.switches.append(switch_socket)
			threading.Thread(target=self.handle_switch, args=(switch_socket, addr)).start()

	def handle_switch(self, switch_socket, addr):
		while not self.stop_event.is_set():
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

	def sync_with_shadow(self, shadow_socket):
		while not self.stop_event.is_set():
			try:
				# Prepare state for transfer
				serializable_switch_table = {key: (value[0], None) for key, value in self.switch_table.items()}
				serializable_frame_buffers = {key: value.decode('utf-8') for key, value in self.frame_buffers.items()}

				state = {
					"switch_table": serializable_switch_table,
					"frame_buffers": serializable_frame_buffers,
					"global_switch_table": self.global_switch_table,
				}

				# Serialize and send state
				shadow_socket.sendall(pickle.dumps(state))
				#print("Backbone: State sent to shadow.")

				# Wait for acknowledgment
				ack = shadow_socket.recv(BUFFER_SIZE)
				'''
				if ack.decode('utf-8') == "ACK":
					print("Backbone: Shadow switch acknowledged state.")
				else:
					print("Backbone: Unexpected response from shadow switch.")
					'''

				time.sleep(0.5)

			except Exception as e:
				print(f"Error in sync_with_shadow: {e}")
				break

	def stop(self):
		self.stop_event.set()
		self.server_socket.close()
		for s in self.switches:
			s.close()

class ShadowSwitch(BackboneSwitch):
	def __init__(self, port: int, shadow_id: int, global_switch_table: dict = {}, switch_table: dict = {}):
		super().__init__(port, global_switch_table, switch_table)
		self.is_active = False
		self.last_heartbeat = time.time()
		self.started = False  # Prevent multiple starts

	def receive_state(self, active_socket, timeout=3):
		active_socket.settimeout(timeout)

		while not self.is_active:
			try:
				state_data = active_socket.recv(BUFFER_SIZE)
				state = pickle.loads(state_data)

				self.switch_table = state.get("switch_table", {})
				self.frame_buffers = {key: value.encode('utf-8') for key, value in state.get("frame_buffers", {}).items()}
				self.global_switch_table = state.get("global_switch_table", {})

				active_socket.sendall(b"ACK")
				#print("Shadow: State updated and acknowledged.")

				self.last_heartbeat = time.time()

			except socket.timeout:
				if time.time() - self.last_heartbeat > timeout:
					print("Active switch unreachable, activating shadow.")
					self.is_active = True
					break
			except Exception as e:
				print(f"Error receiving state in shadow switch: {e}")
				self.is_active = True
				break

		if self.is_active:
			self.start()
