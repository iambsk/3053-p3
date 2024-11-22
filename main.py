import sys
import socket
import time
import threading
import signal
from switch import Switch
from node import Node
from backbone import BackboneSwitch

# Global list to keep track of all threads
threads = []

# Helper function to load firewall rules
def load_firewall_rules(file_path):
    rules = {}
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    rule_key, action = line.strip().split(' ')
                    rules[rule_key] = action
    except FileNotFoundError:
        print(f"Firewall file {file_path} not found. No rules loaded.")
    return rules

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    print("\nInterrupt received, shutting down...")
    for thread in threads:
        if thread.is_alive():
            print(f"Terminating thread {thread.name}")
            thread._stop()  # Forcefully stop the thread
    sys.exit(0)

def main():
    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)

    # Check command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python main.py <number_of_ASs> <number_of_nodes>")
        sys.exit(1)

    num_as = int(sys.argv[1])
    print(f"num_as: {num_as}")
    num_nodes = int(sys.argv[2])
    if not (1 <= num_nodes <= 16):
        print("Number of nodes should be between 1 and 16.")
        sys.exit(1)

    # Load firewall rules
    firewall_rules = load_firewall_rules('firewall.txt')

    # Initialize the backbone switch
    backbone_port = 8001
    backbone_switch = BackboneSwitch(port=backbone_port, firewall_rules=firewall_rules)
    backbone_switch_thread = threading.Thread(target=backbone_switch.start, name="BackboneSwitchThread")
    backbone_switch_thread.start()
    threads.append(backbone_switch_thread)

    # Create switches for each AS
    switch_ports = {}  # Mapping of switch IDs to ports
    for i in range(1, num_as + 1):
        new_id = i
        new_port = backbone_port + i
        switch_ports[new_id] = new_port

    print("Starting switches")
    switches = []
    for switch_id in switch_ports:
        switch = Switch(
            id=switch_id,
            port=switch_ports[switch_id],
            backbone_socket=socket.create_connection(('localhost', backbone_port)),
            firewall_rules=firewall_rules
        )
        switch_thread = threading.Thread(target=switch.start, name=f"SwitchThread-{switch_id}")
        switch_thread.start()
        threads.append(switch_thread)
        switches.append(switch)

    # Set up the switch table for the backbone
    switch_table = {}
    for switch_id in switch_ports:
        switch_table[switch_id] = (('localhost', switch_ports[switch_id]), socket.create_connection(('localhost', switch_ports[switch_id])))
    backbone_switch.set_switch_table(switch_table)
    time.sleep(0.02)

    # Connect nodes to switches
    print(f"Starting {num_nodes} nodes per switch")
    nodes = []
    for i, switch in enumerate(switches):
        for j in range(num_nodes):
            print(f"Starting node {j + 1} on switch {i + 1}")
            node = Node(j + 1, 'localhost', switch.port, i + 1)
            nodes.append(node)
            node.connect_to_switch()
            node_thread = threading.Thread(target=node.receive_data, name=f"NodeReceiveThread-{node.id}")
            node_thread.start()
            threads.append(node_thread)

    print("Starting transmission")
    print(f"{'Network ID':<15}{'Node ID':<10}{'Switch Port':<15}")
    print("-" * 40)
    for node in nodes:
        print(f"{node.network_id:<15}{node.id:<10}{node.switch_port:<15}")

    # Start transmission for all nodes
    for node in nodes:
        send_thread = threading.Thread(target=node.read_input_and_send, name=f"NodeSendThread-{node.id}")
        send_thread.start()
        threads.append(send_thread)

    print("Waiting for transmission to finish")
    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All nodes have finished sending data.")

if __name__ == "__main__":
    main()
