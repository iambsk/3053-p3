import sys
import socket
import time
import threading
import signal
from switch import Switch, ShadowSwitch
from node import Node
from backbone import BackboneSwitch

# Global list to keep track of all threads
threads = []

def signal_handler(sig, frame):
	print("\nInterrupt received, shutting down...")
	for thread in threads:
		if thread.is_alive():
			print(f"Terminating thread {thread.name}")
			thread._stop()	# kill the thread
	sys.exit(0)

def main():
	signal.signal(signal.SIGINT, signal_handler)

	if len(sys.argv) != 3:
		print("Usage: python main.py <number_of_ASs> <number_of_nodes>")
		sys.exit(1)

	num_as = int(sys.argv[1])
	print(f"num_as: {num_as}")
	num_nodes = int(sys.argv[2])
	if not (1 <= num_nodes <= 16):
		print("Number of nodes should be between 1 and 16.")
		sys.exit(1)

	shadow_port = 8001 
	shadow_id = 99 
	backbone_port = 8002
	switch_ports = { # id to port
	}
	for i in range(1, num_as + 1):
		new_id = i
		new_port = backbone_port + i
		switch_ports[new_id] = new_port
	# TODO Create global switch table
	# global_switch_table = {}

	# start the shadow switch
	shadow_switch = ShadowSwitch(shadow_id, shadow_port, backbone_socket=None)
	shadow_thread = threading.Thread(target=shadow_switch.start, name="ShadowSwitchThread")
	shadow_thread.start()
	threads.append(shadow_thread)
	time.sleep(0.1)

	shadow_socket = socket.create_connection(('localhost', shadow_port))
	
	#start the Backbone Switch
	backbone_switch = BackboneSwitch(backbone_port)
	backbone_switch_thread = threading.Thread(target=backbone_switch.start, name="BackboneSwitchThread")
	backbone_switch_thread.start()
	threads.append(backbone_switch_thread)

	sync_thread = threading.Thread(target=backbone_switch.sync_with_shadow, args=(shadow_socket,), name="SyncThread")
	sync_thread.start()
	threads.append(sync_thread)

	print("Starting switches")
	switches = []
	for switch_id in switch_ports:
		switch = Switch(switch_id, switch_ports[switch_id], backbone_socket=socket.create_connection(('localhost', backbone_port)))
		switch_thread = threading.Thread(target=switch.start, name=f"SwitchThread-{switch_id}")
		switch_thread.start()
		threads.append(switch_thread)
		switches.append(switch)

	switch_table = {}
	for switch_id in switch_ports:
		switch_table[switch_id] = (('localhost', switch_ports[switch_id]), socket.create_connection(('localhost', switch_ports[switch_id])))
	backbone_switch.set_switch_table(switch_table)
	time.sleep(0.02)

	# Connect each node
	nodes = []
	#nodes_per_switch = -(-num_nodes // len(switches))	# Number of nodes per switch, rounded up
	nodes_per_switch = num_nodes 
	print(f"Starting {nodes_per_switch} nodes per switch")
	for i, switch in enumerate(switches):
		for j in range(nodes_per_switch):
			print(f"Starting node {j + 1} on switch {i + 1}")
			node = Node(j + 1, 'localhost', switch.port, i + 1)
			nodes.append(node)
			node.connect_to_switch()
			node_thread = threading.Thread(target=node.receive_data, name=f"NodeReceiveThread-{node.id}")
			node_thread.start()
			threads.append(node_thread)
			# time.sleep(0.5)  # dont want all nodes to connect at the same time

	print("Starting transmission")
	print(f"{'Network ID':<15}{'Node ID':<10}{'Switch Port':<15}")
	print("-" * 40)
	for node in nodes:
		print(f"{node.network_id:<15}{node.id:<10}{node.switch_port:<15}")

	# Start transmission
	for node in nodes:
		send_thread = threading.Thread(target=node.read_input_and_send, name=f"NodeSendThread-{node.id}")
		send_thread.start()
		threads.append(send_thread)

	print("Waiting for transmission to finish")

	# Wait for all threads to finish
	for thread in threads:
		thread.join()

	print("All nodes have finished sending data.")

if __name__ == "__main__":
	main()
