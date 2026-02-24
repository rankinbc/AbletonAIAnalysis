"""
Sample-Based Simpler Generator

Creates Ableton Simpler devices pre-loaded with samples.
Supports loading samples from any folder (like Imba Goa Trance Drums).

Usage:
    from sample_generator import SampleGenerator

    gen = SampleGenerator()

    # Create a Simpler with a kick sample
    kick_xml = gen.create_simpler_with_sample(
        sample_path="D:/OneDrive/Music/Projects/Shared/Packs/Samples/Imba Goa Trance Drums Kit/Kicks/Imba Kick 01.wav",
        name="Goa Kick"
    )

    # Create a drum rack with multiple samples
    drum_rack_xml = gen.create_drum_rack({
        36: "Kicks/Imba Kick 01.wav",  # C1 - Kick
        38: "Snares/Imba Snare 01.wav",  # D1 - Snare
        42: "Closed Hats/Imba Closed Hat 01.wav",  # F#1 - Hihat
    }, base_path="D:/OneDrive/Music/Projects/Shared/Packs/Samples/Imba Goa Trance Drums Kit")
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import xml.etree.ElementTree as ET
import random


def path_to_hex(path: str) -> str:
    """Convert a file path to Ableton's hex-encoded format."""
    # Ableton uses UTF-16LE encoding with null terminator
    encoded = path.encode('utf-16-le') + b'\x00\x00'
    return encoded.hex().upper()


def path_to_relative_elements(path: str) -> List[Tuple[int, str]]:
    """Convert path to RelativePathElement list.

    Returns list of (id, dir_name) tuples.
    Empty dir names for parent folder references.
    """
    path = Path(path)
    parts = list(path.parts)

    # For Windows paths like D:\folder\file.wav
    # We need empty elements for drive traversal, then actual folder names
    elements = []
    base_id = random.randint(1000, 9999)

    # Start with empty elements for parent navigation
    # (Ableton uses these to indicate "go up" from project folder)
    for i in range(3):  # Usually 3 empty ones to get to root
        elements.append((base_id + i, ""))

    # Then add actual path components (excluding drive and filename)
    for i, part in enumerate(parts[1:-1]):  # Skip drive letter and filename
        elements.append((base_id + 3 + i, part))

    return elements


def get_file_size(path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(path)
    except:
        return 0


def calculate_crc(path: str, max_size: int = 16384) -> int:
    """Calculate CRC for sample verification (simplified)."""
    try:
        with open(path, 'rb') as f:
            data = f.read(max_size)
            # Simple checksum - Ableton uses a custom CRC
            return sum(data) % 65536
    except:
        return 0


class SampleGenerator:
    """Generate Simpler devices with samples."""

    def __init__(self):
        self.id_counter = random.randint(10000, 50000)

    def _next_id(self) -> int:
        self.id_counter += 1
        return self.id_counter

    def create_file_ref(self, sample_path: str) -> str:
        """Create FileRef XML for a sample."""
        path = Path(sample_path)
        abs_path = str(path.absolute())

        # Get path components
        rel_elements = path_to_relative_elements(abs_path)

        # Build RelativePathElement XML
        rel_path_xml = ""
        for elem_id, dir_name in rel_elements:
            rel_path_xml += f'<RelativePathElement Id="{elem_id}" Dir="{dir_name}" />\n'

        # Build PathHint (simplified version using path parts)
        path_hint_xml = ""
        parts = list(path.parts)
        for i, part in enumerate(parts[1:-1]):  # Skip drive and filename
            path_hint_xml += f'<RelativePathElement Id="{i}" Dir="{part}" />\n'

        # Get file info
        file_size = get_file_size(abs_path)
        crc = calculate_crc(abs_path)
        mod_time = int(time.time())

        # Hex-encode the full path
        hex_data = path_to_hex(abs_path)
        # Format in rows of 80 chars
        hex_rows = [hex_data[i:i+80] for i in range(0, len(hex_data), 80)]
        hex_formatted = "\n".join(hex_rows)

        return f'''<SampleRef>
    <FileRef>
        <HasRelativePath Value="true" />
        <RelativePathType Value="1" />
        <RelativePath>
            {rel_path_xml}
        </RelativePath>
        <Name Value="{path.name}" />
        <Type Value="1" />
        <Data>
            {hex_formatted}
        </Data>
        <RefersToFolder Value="false" />
        <SearchHint>
            <PathHint>
                {path_hint_xml}
            </PathHint>
            <FileSize Value="{file_size}" />
            <Crc Value="{crc}" />
            <MaxCrcSize Value="16384" />
            <HasExtendedInfo Value="true" />
        </SearchHint>
        <LivePackName Value="" />
        <LivePackId Value="" />
    </FileRef>
    <LastModDate Value="{mod_time}" />
    <SourceContext />
    <SampleUsageHint Value="0" />
    <DefaultDuration Value="44100" />
    <DefaultSampleRate Value="44100" />
</SampleRef>'''

    def create_simpler_with_sample(self, sample_path: str, name: str = None) -> str:
        """Create a Simpler device XML with a sample loaded.

        Args:
            sample_path: Full path to .wav file
            name: Display name for the device (defaults to sample name)

        Returns:
            XML string for the Simpler device
        """
        if name is None:
            name = Path(sample_path).stem

        sample_ref = self.create_file_ref(sample_path)
        device_id = self._next_id()

        return f'''<OriginalSimpler Id="{device_id}">
    <LomId Value="0" />
    <LomIdView Value="0" />
    <IsExpanded Value="true" />
    <On>
        <LomId Value="0" />
        <Manual Value="true" />
        <AutomationTarget Id="{self._next_id()}">
            <LockEnvelope Value="0" />
        </AutomationTarget>
        <MidiCCOnOffThresholds>
            <Min Value="64" />
            <Max Value="127" />
        </MidiCCOnOffThresholds>
    </On>
    <ModulationSourceCount Value="0" />
    <ParametersListWrapper LomId="0" />
    <Pointee Id="{self._next_id()}" />
    <LastSelectedTimeableIndex Value="0" />
    <LastSelectedClipEnvelopeIndex Value="0" />
    <LastPresetRef>
        <Value />
    </LastPresetRef>
    <LockedScripts />
    <IsFolded Value="false" />
    <ShouldShowPresetName Value="true" />
    <UserName Value="{name}" />
    <Annotation Value="" />
    <SourceContext />
    <OverwriteProtectionNumber Value="2561" />
    <Player>
        <MultiSampleMap>
            <SampleParts>
                <MultiSamplePart Id="{self._next_id()}" HasImportedSlicePoints="false" NeedsAnalysisData="false">
                    <LomId Value="0" />
                    <Name Value="{name}" />
                    <Selection Value="true" />
                    <IsActive Value="true" />
                    <Solo Value="false" />
                    <KeyRange>
                        <Min Value="0" />
                        <Max Value="127" />
                        <CrossfadeMin Value="0" />
                        <CrossfadeMax Value="127" />
                    </KeyRange>
                    <VelocityRange>
                        <Min Value="1" />
                        <Max Value="127" />
                        <CrossfadeMin Value="1" />
                        <CrossfadeMax Value="127" />
                    </VelocityRange>
                    <SelectorRange>
                        <Min Value="0" />
                        <Max Value="127" />
                        <CrossfadeMin Value="0" />
                        <CrossfadeMax Value="127" />
                    </SelectorRange>
                    <RootKey Value="60" />
                    <Detune Value="0" />
                    <TuneScale Value="100" />
                    <Panorama Value="0" />
                    <Volume Value="1" />
                    <Link Value="false" />
                    {sample_ref}
                    <SlicingThreshold Value="100" />
                    <SlicingBeatGrid Value="4" />
                    <SlicingRegions Value="8" />
                    <SlicingStyle Value="0" />
                    <SampleWarpProperties>
                        <WarpMarkers>
                            <WarpMarker Id="0" SecTime="0" BeatTime="0" />
                        </WarpMarkers>
                        <WarpMode Value="0" />
                        <GranularityTones Value="30" />
                        <GranularityTexture Value="65" />
                        <FluctuationTexture Value="25" />
                        <ComplexProFormants Value="100" />
                        <ComplexProEnvelope Value="128" />
                        <TransientResolution Value="6" />
                        <TransientLoopMode Value="2" />
                        <TransientEnvelope Value="100" />
                        <IsWarped Value="false" />
                        <Onsets />
                        <TimeSignature>
                            <TimeSignatures>
                                <RemoteableTimeSignature Id="0">
                                    <Numerator Value="4" />
                                    <Denominator Value="4" />
                                    <Time Value="0" />
                                </RemoteableTimeSignature>
                            </TimeSignatures>
                        </TimeSignature>
                        <BeatGrid>
                            <FixedNumerator Value="1" />
                            <FixedDenominator Value="16" />
                            <GridIntervalPixel Value="20" />
                            <Ntoles Value="2" />
                            <SnapToGrid Value="true" />
                            <Fixed Value="false" />
                        </BeatGrid>
                    </SampleWarpProperties>
                    <SlicePoints />
                    <ManualSlicePoints />
                    <BeatSlicePoints />
                    <RegionSlicePoints />
                    <UseDynamicBeatSlices Value="true" />
                    <UseDynamicRegionSlices Value="true" />
                </MultiSamplePart>
            </SampleParts>
        </MultiSampleMap>
    </Player>
    <AmpEnvelope>
        <IsOn Value="true" />
        <AttackTime Value="0.0001" />
        <AttackLevel Value="1" />
        <AttackSlope Value="0" />
        <DecayTime Value="1" />
        <DecayLevel Value="1" />
        <DecaySlope Value="-0.8" />
        <SustainLevel Value="1" />
        <ReleaseTime Value="0.05" />
        <ReleaseLevel Value="0" />
        <ReleaseSlope Value="-0.5" />
        <LoopMode Value="4" />
        <Loop>
            <SustainLoop>
                <Start Value="0" />
                <End Value="1" />
                <Mode Value="0" />
                <Crossfade Value="0" />
                <Detune Value="0" />
            </SustainLoop>
            <ReleaseLoop>
                <Start Value="0" />
                <End Value="1" />
                <Mode Value="0" />
                <Crossfade Value="0" />
                <Detune Value="0" />
            </ReleaseLoop>
        </Loop>
        <FreeRun Value="false" />
        <Legato Value="false" />
        <LinkedVelocityAmount Value="0" />
    </AmpEnvelope>
    <SimplerFilter>
        <IsOn Value="false" />
        <Type Value="0" />
        <Freq Value="500" />
        <Res Value="0.5" />
        <FreqModByVel Value="0" />
        <FreqModByKey Value="0" />
        <LFOAmount Value="0" />
        <EnvAmount Value="0" />
        <MorphAmount Value="0" />
        <Drive Value="0" />
        <Circuit Value="0" />
        <Legacy Value="false" />
        <IsSlope24dB Value="true" />
    </SimplerFilter>
    <FilterEnvelope>
        <IsOn Value="false" />
        <AttackTime Value="0.001" />
        <AttackLevel Value="1" />
        <AttackSlope Value="0" />
        <DecayTime Value="0.5" />
        <DecayLevel Value="1" />
        <DecaySlope Value="-0.5" />
        <SustainLevel Value="0" />
        <ReleaseTime Value="0.1" />
        <ReleaseLevel Value="0" />
        <ReleaseSlope Value="-0.5" />
        <LoopMode Value="4" />
        <Loop>
            <SustainLoop>
                <Start Value="0" />
                <End Value="1" />
                <Mode Value="0" />
                <Crossfade Value="0" />
                <Detune Value="0" />
            </SustainLoop>
            <ReleaseLoop>
                <Start Value="0" />
                <End Value="1" />
                <Mode Value="0" />
                <Crossfade Value="0" />
                <Detune Value="0" />
            </ReleaseLoop>
        </Loop>
        <FreeRun Value="false" />
        <Legato Value="false" />
        <LinkedVelocityAmount Value="0" />
    </FilterEnvelope>
    <Lfo>
        <IsOn Value="false" />
        <Type Value="0" />
        <Speed Value="1" />
        <Phase Value="0" />
        <Offset Value="0" />
        <Retrigger Value="true" />
        <KeySync Value="false" />
    </Lfo>
    <SimplerPitch>
        <TransposeKey Value="0" />
        <TransposeFine Value="0" />
        <PitchModByLfo Value="0" />
        <Glide Value="false" />
        <GlideTime Value="0.1" />
        <Spread Value="0" />
    </SimplerPitch>
    <VoiceSettings>
        <Voices Value="1" />
        <RetriggerMode Value="0" />
    </VoiceSettings>
    <GlobalVolume Value="0" />
    <GlobalVolumeModByVel Value="0.4" />
    <Pan Value="0" />
    <PlaybackMode Value="0" />
    <Reverse Value="false" />
    <Snap Value="false" />
    <SampleSelector Value="0" />
    <ViewSettings>
        <SelectedPage Value="0" />
    </ViewSettings>
</OriginalSimpler>'''

    def create_drum_pad(self, sample_path: str, note: int, name: str = None) -> str:
        """Create a DrumBranch (drum pad) with a Simpler."""
        if name is None:
            name = Path(sample_path).stem

        simpler_xml = self.create_simpler_with_sample(sample_path, name)
        branch_id = self._next_id()

        return f'''<DrumBranch Id="{branch_id}">
    <LomId Value="0" />
    <Name Value="{name}" />
    <IsSelected Value="false" />
    <DeviceChain>
        <Devices>
            {simpler_xml}
        </Devices>
        <MidiToAudioRouting Value="true" />
    </DeviceChain>
    <ReceivingNote Value="{note}" />
</DrumBranch>'''

    def create_drum_rack(self,
                          samples: Dict[int, str],
                          base_path: str = None,
                          name: str = "Drum Rack") -> str:
        """Create a Drum Rack with multiple samples.

        Args:
            samples: Dict mapping MIDI note (36=C1, 38=D1, etc.) to sample path
            base_path: Optional base path to prepend to sample paths
            name: Name for the drum rack

        Returns:
            XML string for DrumGroupDevice

        Example:
            create_drum_rack({
                36: "Kicks/Kick 01.wav",
                38: "Snares/Snare 01.wav",
                42: "Hats/Hat 01.wav",
            }, base_path="D:/Samples/Drums")
        """
        drum_branches = ""
        for note, sample in sorted(samples.items()):
            if base_path:
                full_path = str(Path(base_path) / sample)
            else:
                full_path = sample
            drum_branches += self.create_drum_pad(full_path, note)

        rack_id = self._next_id()

        return f'''<DrumGroupDevice Id="{rack_id}">
    <LomId Value="0" />
    <LomIdView Value="0" />
    <IsExpanded Value="true" />
    <On>
        <LomId Value="0" />
        <Manual Value="true" />
        <AutomationTarget Id="{self._next_id()}">
            <LockEnvelope Value="0" />
        </AutomationTarget>
        <MidiCCOnOffThresholds>
            <Min Value="64" />
            <Max Value="127" />
        </MidiCCOnOffThresholds>
    </On>
    <ModulationSourceCount Value="0" />
    <ParametersListWrapper LomId="0" />
    <Pointee Id="{self._next_id()}" />
    <LastSelectedTimeableIndex Value="0" />
    <LastSelectedClipEnvelopeIndex Value="0" />
    <LastPresetRef>
        <Value />
    </LastPresetRef>
    <LockedScripts />
    <IsFolded Value="false" />
    <ShouldShowPresetName Value="true" />
    <UserName Value="{name}" />
    <Annotation Value="" />
    <SourceContext />
    <OverwriteProtectionNumber Value="2561" />
    <Branches>
        {drum_branches}
    </Branches>
    <IsBranchesListVisible Value="true" />
    <IsReturnBranchesListVisible Value="false" />
    <IsSendBranchesListVisible Value="false" />
    <SelectedDrumPadIndex Value="0" />
</DrumGroupDevice>'''


# =============================================================================
# DRUM KIT PRESETS
# =============================================================================

IMBA_GOA_TRANCE_PATH = r"D:\OneDrive\Music\Projects\Shared\Packs\Samples\Imba Goa Trance Drums Kit"

def create_goa_trance_kit(kick_num: int = 1,
                           clap_num: int = 1,
                           hat_num: int = 1,
                           snare_num: int = 1) -> str:
    """Create a Drum Rack with Imba Goa Trance samples.

    Args:
        kick_num: Kick sample number (1-64)
        clap_num: Clap sample number (1-13)
        hat_num: Closed hat sample number (1-56)
        snare_num: Snare sample number (1-??)

    Returns:
        DrumGroupDevice XML
    """
    gen = SampleGenerator()

    samples = {
        36: f"Kicks/Imba Kick {kick_num:02d}.wav",      # C1 - Kick
        38: f"Snares/Imba Snare {snare_num:02d}.wav",   # D1 - Snare
        39: f"Claps/Imba Clap {clap_num:02d}.wav",      # D#1 - Clap
        42: f"Closed Hats/Imba Closed Hat {hat_num:02d}.wav",  # F#1 - Closed Hat
    }

    return gen.create_drum_rack(samples, IMBA_GOA_TRANCE_PATH, "Goa Trance Kit")


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Sample-Based Simpler Generator')
    subparsers = parser.add_subparsers(dest='command')

    # Create simpler
    simpler_parser = subparsers.add_parser('simpler', help='Create a Simpler with sample')
    simpler_parser.add_argument('sample', help='Path to sample file')
    simpler_parser.add_argument('--name', '-n', help='Device name')
    simpler_parser.add_argument('--output', '-o', help='Output XML file')

    # Create drum rack
    rack_parser = subparsers.add_parser('drumrack', help='Create a Drum Rack')
    rack_parser.add_argument('--kick', '-k', type=int, default=1, help='Kick number (1-64)')
    rack_parser.add_argument('--clap', '-c', type=int, default=1, help='Clap number (1-13)')
    rack_parser.add_argument('--hat', '-H', type=int, default=1, help='Hat number (1-56)')
    rack_parser.add_argument('--snare', '-s', type=int, default=1, help='Snare number')
    rack_parser.add_argument('--output', '-o', help='Output XML file')

    # List samples
    list_parser = subparsers.add_parser('list', help='List available samples')
    list_parser.add_argument('category', nargs='?', choices=['kicks', 'claps', 'hats', 'snares'],
                             help='Category to list')

    args = parser.parse_args()

    if args.command == 'simpler':
        gen = SampleGenerator()
        xml = gen.create_simpler_with_sample(args.sample, args.name)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(xml)
            print(f"Simpler XML saved to: {args.output}")
        else:
            print(xml)

    elif args.command == 'drumrack':
        xml = create_goa_trance_kit(args.kick, args.clap, args.hat, args.snare)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(xml)
            print(f"Drum Rack XML saved to: {args.output}")
        else:
            print(xml[:2000])
            print("\n... (truncated)")
            print(f"\nTotal XML length: {len(xml)} chars")

    elif args.command == 'list':
        base = Path(IMBA_GOA_TRANCE_PATH)
        categories = {
            'kicks': 'Kicks',
            'claps': 'Claps',
            'hats': 'Closed Hats',
            'snares': 'Snares',
        }

        if args.category:
            folder = base / categories[args.category]
            if folder.exists():
                samples = sorted(folder.glob('*.wav'))
                print(f"\n{args.category.upper()} ({len(samples)} samples):")
                for s in samples[:20]:
                    print(f"  {s.name}")
                if len(samples) > 20:
                    print(f"  ... and {len(samples) - 20} more")
        else:
            print(f"\nImba Goa Trance Drum Kit")
            print(f"Location: {base}")
            print()
            for cat, folder_name in categories.items():
                folder = base / folder_name
                if folder.exists():
                    count = len(list(folder.glob('*.wav')))
                    print(f"  {cat}: {count} samples")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
