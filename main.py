import sys
import socket
import time
import threading
from hub import Hub
from node import Node
from backbone import BackboneHub

def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <number_of_nodes>")
        return

    num_nodes = int(sys.argv[1])
    if not (2 <= num_nodes <= 255):
        print("Number of nodes should be between 2 and 255.")
        return

    backbone_port = 8001
    switches = { # id to port
        2: 8002,
        3: 8003,
        4: 8004
    }
    # TODO Create global switch table
    global_switch_table = {}
    switch_table = {}
    for switch_id in switches:
        switch_table[switch_id] = (('localhost', switches[switch_id]), socket.create_connection(('localhost', switches[switch_id])))
    hub_thread = threading.Thread(target=BackboneHub, args=(backbone_port, global_switch_table, switch_table))
    hub_thread.start()
    print("Starting switches")
    switches = []
    for switch_id in switches:
        switch = Hub(switches[switch_id], backbone_socket=socket.create_connection(('localhost', backbone_port)))
        threading.Thread(target=switch.start).start()
        switches.append(switch)

    time.sleep(1)
    print("Starting nodes")
    # Connect each node
    nodes = []
    node_threads = []
    nodes_per_switch = num_nodes // len(switches)  # Number of nodes per switch
    for i, switch in enumerate(switches):
        for j in range(nodes_per_switch):
            node_id = i * nodes_per_switch + j + 1
            node = Node(node_id, 'localhost', switch.port)
            nodes.append(node)
            node.connect_to_switch()
            node_thread = threading.Thread(target=node.receive_data)
            node_thread.start()
            node_threads.append(node_thread)
            time.sleep(0.5)  # dont want all nodes to connect at the same time
    print("Starting transmission")
    # Start transmission
    send_threads = []
    for node in nodes:
        send_thread = threading.Thread(target=node.read_input_and_send)
        send_thread.start()
        send_threads.append(send_thread)
    print("Waiting for transmission to finish")
    # Wait for all send threads to finish before joining receive threads
    for send_thread in send_threads:
        send_thread.join()
    print("Waiting for receive threads to finish")
    # close all node_threads
    for node_thread in node_threads:
        node_thread.join()

    print("All nodes have finished sending data.")

if __name__ == "__main__":
    main()