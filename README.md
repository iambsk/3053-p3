# 3053-p2

Group Members:
- Brian Kessel
- Max Strack
- Ben Mannal

Git Repo: https://github.com/iambsk/3053-p3

## How to run

1. Run `python nodeGenerator.py <number of ASes> <number of nodes>`
2. Run `python main.py <number of ASes> <number of nodes>`

To test the shadow switch, uncomment line 140-147 in main.py and rerun the program.

## Files

- `nodeGenerator.py`: Generates the node files for the given number of ASes and nodes.
- `main.py`: Runs the program.
- `node.py`: The node class 
- `firewall.py` the class for the Firewall, currently not used
- `switch.py` the class for the switch, which handles routing and firewall rules
- `backbone.py` the backbone class, which handles the backbone network. Also contains the shadow switch
- `firewall.txt` the firewall rules 1_1_1_2 Block means block the connection from node 1 in AS 1 to node 2 in AS 1


## Checklist

All functionality works as expected. 
