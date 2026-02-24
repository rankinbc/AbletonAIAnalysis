"""Debug .als file issues."""
import gzip
import xml.etree.ElementTree as ET
from collections import Counter

# Check base template
base_path = r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Base_Template Project\Base_Template.als"
gen_path = r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Paraglide_Style_v2\Paraglide_Style_v2.als"

def check_file(path, name):
    print(f"=== {name} ===")
    with gzip.open(path, 'rb') as f:
        content = f.read().decode('utf-8')
    print(f"Size: {len(content)} chars")

    root = ET.fromstring(content)

    # Check locators
    locators = root.findall(".//Locator")
    print(f"Locators: {len(locators)}")
    for loc in locators:
        loc_id = loc.get('Id')
        time_elem = loc.find('Time')
        name_elem = loc.find('Name')
        time_val = time_elem.get('Value') if time_elem is not None else '?'
        name_val = name_elem.get('Value') if name_elem is not None else '?'
        print(f"  Locator Id={loc_id}, Time={time_val}, Name={name_val}")

    # Check for duplicate IDs
    all_ids = []
    for elem in root.iter():
        if 'Id' in elem.attrib:
            all_ids.append(elem.attrib['Id'])

    id_counts = Counter(all_ids)
    duplicates = {k: v for k, v in id_counts.items() if v > 1}
    print(f"Total IDs: {len(all_ids)}")
    print(f"Unique IDs: {len(id_counts)}")
    print(f"Duplicate ID values: {len(duplicates)}")
    if duplicates:
        print(f"  Duplicated IDs: {sorted(duplicates.keys())}")

    return root, duplicates

print("Checking BASE template:")
base_root, base_dups = check_file(base_path, "BASE TEMPLATE")

print("\n")

print("Checking GENERATED file:")
gen_root, gen_dups = check_file(gen_path, "GENERATED FILE")

# Compare duplicates
print("\n=== COMPARISON ===")
base_set = set(base_dups.keys())
gen_set = set(gen_dups.keys())
print(f"Only in BASE: {sorted(base_set - gen_set)}")
print(f"Only in GENERATED: {sorted(gen_set - base_set)}")
print(f"Common duplicates: {sorted(base_set & gen_set)}")

# Check file sizes and first few elements
print("\n=== STRUCTURE CHECK ===")
# Check for Ableton tag
ableton_base = base_root.find(".")
ableton_gen = gen_root.find(".")
print(f"Base root tag: {base_root.tag}, attribs: {list(base_root.attrib.keys())}")
print(f"Gen root tag: {gen_root.tag}, attribs: {list(gen_root.attrib.keys())}")

# Check LiveSet
live_set_base = base_root.find("LiveSet")
live_set_gen = gen_root.find("LiveSet")
print(f"Base LiveSet children: {[c.tag for c in live_set_base][:10]}")
print(f"Gen LiveSet children: {[c.tag for c in live_set_gen][:10]}")

# Check for any extra/missing children
base_children = set(c.tag for c in live_set_base)
gen_children = set(c.tag for c in live_set_gen)
print(f"Only in BASE LiveSet: {base_children - gen_children}")
print(f"Only in GEN LiveSet: {gen_children - base_children}")

# Check NextPointeeId - critical for Ableton
next_id_base = live_set_base.find("NextPointeeId")
next_id_gen = live_set_gen.find("NextPointeeId")
print(f"\nNextPointeeId BASE: {next_id_base.get('Value') if next_id_base is not None else 'MISSING'}")
print(f"NextPointeeId GEN: {next_id_gen.get('Value') if next_id_gen is not None else 'MISSING'}")

# Check max ID used
all_base_ids = [int(e.get('Id')) for e in base_root.iter() if e.get('Id') and e.get('Id').isdigit()]
all_gen_ids = [int(e.get('Id')) for e in gen_root.iter() if e.get('Id') and e.get('Id').isdigit()]
print(f"Max ID in BASE: {max(all_base_ids) if all_base_ids else 0}")
print(f"Max ID in GEN: {max(all_gen_ids) if all_gen_ids else 0}")
