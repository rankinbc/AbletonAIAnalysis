"""Patch madmom for Python 3.10+ and NumPy 2.0+ compatibility."""
import os
import re

madmom_path = r'C:\Users\badmin\AppData\Roaming\Python\Python313\site-packages\madmom'

patched_count = 0

for root, dirs, files in os.walk(madmom_path):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                original = content

                # Fix deprecated numpy types
                content = re.sub(r'\bnp\.float\b(?!64|32|16)', 'np.float64', content)
                content = re.sub(r'\bnp\.int\b(?!64|32|16|8)', 'np.int64', content)

                # Fix collections.MutableSequence -> collections.abc.MutableSequence
                content = content.replace(
                    'from collections import MutableSequence',
                    'from collections.abc import MutableSequence'
                )

                if content != original:
                    print(f'Patching: {os.path.relpath(filepath, madmom_path)}')
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patched_count += 1

            except Exception as e:
                print(f'Error with {filepath}: {e}')

print(f'\nPatched {patched_count} files')
