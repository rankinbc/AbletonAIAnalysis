import gzip
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Generator_Simple\Generator_Simple.als"

with gzip.open(path, 'rb') as f:
    content = f.read().decode('utf-8')

# Find track names
tracks = re.findall(r'<EffectiveName Value="([^"]+)"', content)
print('Tracks:')
for i, t in enumerate(tracks[:15]):
    print(f'  {i+1}. {t}')

# Check if any devices exist
device_types = re.findall(r'<(Operator|OriginalSimpler|Wavetable|DrumGroupDevice|InstrumentGroupDevice|Eq8|Compressor2|AutoFilter|Reverb|Delay|Chorus2)', content)
print(f'\nInstruments/Effects found: {len(device_types)}')
if device_types:
    from collections import Counter
    for d, c in Counter(device_types).items():
        print(f'  - {d}: {c}')
