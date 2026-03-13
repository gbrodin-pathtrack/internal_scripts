import re
import argparse
 
def parse_map_file(map_file, target_file):
    with open(map_file, 'r') as file:
        lines = file.readlines()
 
    total_size = 0
    section_sizes = {'text': 0, 'rodata': 0, 'data': 0, 'bss': 0}
 
    current_section = None
    for line in lines:
        # Detect section headers
        section_match = re.match(r'^\s*\.(\w+)\s+0x[0-9a-fA-F]+\s+0x([0-9a-fA-F]+)', line)
        if section_match:
            current_section = section_match.group(1)
 
        # Detect symbols in sections
        if current_section and target_file in line:
            size_match = re.match(r'^\s*0x[0-9a-fA-F]+\s+0x([0-9a-fA-F]+)', line)
            if size_match:
                size = int(size_match.group(1), 16)
                if current_section in section_sizes:
                    section_sizes[current_section] += size
 
    for section, size in section_sizes.items():
        if section != 'bss':  # Exclude .bss from the total size if it should not be counted
            total_size += size
        print(f'Section .{section}: {size} bytes')
 
    print(f'Total size used by {target_file}: {total_size} bytes')
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate memory usage from .map file.")
    parser.add_argument("map_file", help="The .map file to parse")
    parser.add_argument("target_file", help="The target file to analyze (e.g., main.o)")
 
    args = parser.parse_args()
    parse_map_file(args.map_file, args.target_file)
