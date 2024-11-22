class Firewall:
    def __init__(self, rules_file):
        self.rules = self.load_rules(rules_file)

    def load_rules(self, file_path):
        rules = {}
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    src_dest, action = line.strip().split(' ')
                    rules[src_dest] = action
        return rules

    def is_allowed(self, src_network, src_node, dest_network, dest_node):
        key = f"{src_network}_{src_node}_{dest_network}_{dest_node}"
        return self.rules.get(key, "Allow") != "Block"
