import sys

def generate_files(num_networks, num_nodes):
    for network in range(1, num_networks + 1):
        for node in range(1, num_nodes + 1):
            with open(f"node{network}_{node}.txt", "w") as file:
                for other_node in range(1, num_nodes + 1):
                    if node != other_node:  # Exclude itself
                        file.write(f"{other_node}_{network}: {node} to {other_node}_{network}\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python nodeGen.py num_networks num_nodes")
    else:
        try:
            num_networks = int(sys.argv[1])
            num_nodes = int(sys.argv[2])
            generate_files(num_networks, num_nodes)
            print(f"Generated {num_networks * num_nodes} files successfully.")
        except ValueError:
            print("Please provide an integer as the argument.")

