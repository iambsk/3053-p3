import sys

def generate_files(x):
    for i in range(1, x + 1):
        with open(f"node{i}.txt", "w") as file:
            for j in range(1, x + 1):
                if i != j:  # Exclude itself
                    file.write(f"{j}: {i} to {j}\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python nodeGen.py <x>")
    else:
        try:
            x = int(sys.argv[1])
            generate_files(x)
            print(f"Generated {x} files successfully.")
        except ValueError:
            print("Please provide an integer as the argument.")

