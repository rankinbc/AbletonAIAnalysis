"""
base_template.py
================
Generates a dependable, empty Ableton 11 Live Suite base template (.als).

Designed to be the foundation for any generator project.  Import the
building-block functions directly, or run as a script to write a blank
project to disk.

Usage
-----
    python base_template.py                        # → base_template.als
    python base_template.py -o my_project.als --bpm 140 --tracks 8

Architecture
------------
Every element is built as an explicit XML string, not via ElementTree, so
the node order is always exactly what Ableton expects.  A global ID counter
ensures every node that Ableton might want to automate gets a unique Id.

The public surface you'll use when building on top of this:
    new_id()              → next unique integer ID
    xml_escape(s)         → escape &, <, >, " for XML attribute values
    midi_track(...)       → full <MidiTrack> string
    audio_track(...)      → full <AudioTrack> string
    return_track(...)     → full <ReturnTrack> string
    master_track(bpm)     → <MasterTrack> string
    scene(i, name)        → <Scene> string
    build_als(...)        → write the finished .als to disk
"""

from __future__ import annotations

import gzip
import math
import re
import sys
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Global ID counter
# Every XML node that Live might automate needs a unique Id.
# Call new_id() once per node, never reuse.
# ─────────────────────────────────────────────────────────────────────────────

_id_counter: int = 1

def new_id() -> int:
    global _id_counter
    v = _id_counter
    _id_counter += 1
    return v

def reset_ids() -> None:
    """Reset counter — call before generating a new file."""
    global _id_counter
    _id_counter = 1


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def xml_escape(s: str) -> str:
    """Escape a string for use inside an XML attribute value."""
    return (s
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _indent(xml: str, level: int = 0) -> str:
    """Lightweight pretty-printer — not required for validity but aids debugging."""
    pad = "  " * level
    return "\n".join(pad + line for line in xml.splitlines())


# ─────────────────────────────────────────────────────────────────────────────
# Mixer block (shared by MIDI, Audio, and Return tracks)
# ─────────────────────────────────────────────────────────────────────────────

def _mixer(volume: float = 1.0, pan: float = 0.0,
           num_sends: int = 2, is_return: bool = False) -> str:
    """
    Build a <Mixer> block.

    num_sends   — how many send slots to create (must match the number of
                  Return tracks in the project).
    is_return   — Return tracks don't get send slots back to themselves in
                  Live's UI, but they still need the Sends element.
    """
    sends = "\n".join(
        f"""            <TrackSendHolder Id="{i}">
              <Send>
                <LomId Value="0" />
                <Manual Value="0" />
                <AutomationTarget Id="{new_id()}" />
                <ModulationTarget Id="{new_id()}" />
              </Send>
              <Active Value="true" />
            </TrackSendHolder>"""
        for i in range(num_sends)
    )

    return f"""        <Mixer>
          <LomId Value="0" />
          <LomIdView Value="0" />
          <IsExpanded Value="true" />
          <On>
            <LomId Value="0" />
            <Manual Value="true" />
            <AutomationTarget Id="{new_id()}" />
            <ModulationTarget Id="{new_id()}" />
          </On>
          <ModulationSourceCount Value="0" />
          <ParametersListWrapper LomId="0" />
          <Pointee Id="{new_id()}" />
          <LastSelectedTimeableIndex Value="0" />
          <LastSelectedClipEnvelopeIndex Value="0" />
          <LastSelectedControlEnvelopeIndex Value="0" />
          <Volume>
            <LomId Value="0" />
            <Manual Value="{volume}" />
            <AutomationTarget Id="{new_id()}" />
            <ModulationTarget Id="{new_id()}" />
          </Volume>
          <Pan>
            <LomId Value="0" />
            <Manual Value="{pan}" />
            <AutomationTarget Id="{new_id()}" />
            <ModulationTarget Id="{new_id()}" />
          </Pan>
          <SpeakerOn Value="true" />
          <SoloSink Value="false" />
          <PanMode Value="0" />
          <Sends>
{sends}
          </Sends>
          <Cue>
            <LomId Value="0" />
            <Manual Value="0" />
            <AutomationTarget Id="{new_id()}" />
            <ModulationTarget Id="{new_id()}" />
          </Cue>
          <VolumeModulationTarget Id="{new_id()}" />
          <PanModulationTarget Id="{new_id()}" />
        </Mixer>"""


# ─────────────────────────────────────────────────────────────────────────────
# Clip slot list (8 slots, all empty — fill slot 0 via the midi_clip helper)
# ─────────────────────────────────────────────────────────────────────────────

def _empty_clip_slot_list(num_slots: int = 8) -> str:
    slots = "\n".join(
        f"""      <ClipSlot Id="{i}">
        <ClipSlot>
          <LomId Value="0" />
          <HasStop Value="true" />
          <NeedRerecord Value="false" />
          <Value />
          <IsPlaying Value="false" />
          <IsRecording Value="false" />
        </ClipSlot>
      </ClipSlot>"""
        for i in range(num_slots)
    )
    return f"    <ClipSlotList>\n{slots}\n    </ClipSlotList>"


def _clip_slot_list_with_clip(clip_xml: str,
                               num_slots: int = 8) -> str:
    """Slot 0 holds the clip; the rest are empty."""
    first = f"""      <ClipSlot Id="0">
        <ClipSlot>
          <LomId Value="0" />
          <HasStop Value="true" />
          <NeedRerecord Value="false" />
          <Value>
{clip_xml}
          </Value>
          <IsPlaying Value="false" />
          <IsRecording Value="false" />
        </ClipSlot>
      </ClipSlot>"""

    rest = "\n".join(
        f"""      <ClipSlot Id="{i}">
        <ClipSlot>
          <LomId Value="0" />
          <HasStop Value="true" />
          <NeedRerecord Value="false" />
          <Value />
          <IsPlaying Value="false" />
          <IsRecording Value="false" />
        </ClipSlot>
      </ClipSlot>"""
        for i in range(1, num_slots)
    )

    return f"    <ClipSlotList>\n{first}\n{rest}\n    </ClipSlotList>"


# ─────────────────────────────────────────────────────────────────────────────
# Sequencer blocks (MainSequencer + FreezeSequencer — required on every track)
# ─────────────────────────────────────────────────────────────────────────────

def _sequencer_block(tag: str) -> str:
    return f"""        <{tag}>
          <LomId Value="0" />
          <LomIdView Value="0" />
          <IsExpanded Value="true" />
          <On>
            <LomId Value="0" />
            <Manual Value="true" />
            <AutomationTarget Id="{new_id()}" />
            <ModulationTarget Id="{new_id()}" />
          </On>
          <ModulationSourceCount Value="0" />
          <ParametersListWrapper LomId="0" />
          <Pointee Id="{new_id()}" />
          <LastSelectedTimeableIndex Value="0" />
          <LastSelectedClipEnvelopeIndex Value="0" />
          <LastSelectedControlEnvelopeIndex Value="0" />
          <IsFolded Value="false" />
          <ShouldShowPresetName Value="false" />
          <UserName Value="" />
          <Annotation Value="" />
          <SourceContext />
          <ClipSlotList>
            <ClipSlot Id="0">
              <ClipSlot>
                <LomId Value="0" />
                <HasStop Value="false" />
                <NeedRerecord Value="false" />
                <Value />
                <IsPlaying Value="false" />
                <IsRecording Value="false" />
              </ClipSlot>
            </ClipSlot>
          </ClipSlotList>
          <MonitoringEnum Value="1" />
        </{tag}>"""


# ─────────────────────────────────────────────────────────────────────────────
# MIDI note helpers
# ─────────────────────────────────────────────────────────────────────────────

def midi_note_events(events: List[tuple]) -> str:
    """
    Convert a list of (time, duration, velocity) tuples to MidiNoteEvent XML.
    Used inside a KeyTrack block.
    """
    return "\n".join(
        f'                  <MidiNoteEvent Time="{t:.6f}" Duration="{d:.6f}" '
        f'Velocity="{int(v)}" VelocityDeviation="0" ReleaseVelocity="64" '
        f'OffVelocity="64" Probability="1" IsEnabled="true" NoteId="{new_id()}" />'
        for t, d, v in events
    )


def midi_clip(events_by_pitch: dict, length: float,
              name: str = "Clip", color: int = 0) -> str:
    """
    Build a <MidiClip> XML string.

    events_by_pitch  — {pitch_int: [(time, duration, velocity), ...]}
    length           — clip length in beats
    name             — clip name shown in Ableton
    color            — Ableton colour integer
    """
    key_tracks = ""
    for pitch in sorted(events_by_pitch):
        ne = midi_note_events(events_by_pitch[pitch])
        key_tracks += f"""
                <KeyTrack Id="{new_id()}">
                  <MidiKey Value="{pitch}" />
                  <Notes>
{ne}
                  </Notes>
                  <NoteToMidiRouting />
                  <Enabled Value="true" />
                  <Selected Value="false" />
                </KeyTrack>"""

    safe_name = xml_escape(name)
    clip_id   = new_id()

    return f"""            <MidiClip Id="{clip_id}" Time="0">
              <LomId Value="0" />
              <LomIdView Value="0" />
              <CurrentStart Value="0" />
              <CurrentEnd Value="{length}" />
              <Loop>
                <LoopStart Value="0" />
                <LoopEnd Value="{length}" />
                <StartRelative Value="0" />
                <LoopOn Value="true" />
                <OutMarker Value="{length}" />
                <HiddenLoopStart Value="0" />
                <HiddenLoopEnd Value="{length}" />
              </Loop>
              <Name Value="{safe_name}" />
              <Annotation Value="" />
              <Color Value="{color}" />
              <LaunchMode Value="0" />
              <LaunchQuantisation Value="0" />
              <TimeSignature>
                <TimeSignatures>
                  <RemoteableTimeSignature Id="0">
                    <Numerator Value="4" />
                    <Denominator Value="4" />
                    <Time Value="0" />
                  </RemoteableTimeSignature>
                </TimeSignatures>
              </TimeSignature>
              <Envelopes><Envelopes /></Envelopes>
              <ScrollerTimePreserver><ScrollerTimePreserver /></ScrollerTimePreserver>
              <TimeSelection>
                <AnchorTime Value="0" />
                <OtherTime Value="0" />
              </TimeSelection>
              <Legato Value="false" />
              <Ram Value="false" />
              <SnapToGrid Value="true" />
              <ManualWarp Value="false" />
              <SpliceSlot Value="-1" />
              <IsWarped Value="true" />
              <TakeLanes><TakeLaneList LomId="0" /></TakeLanes>
              <NoteSpellingPreference Value="3" />
              <PreferFlatRootNote Value="false" />
              <ExpressionGrid>
                <FixedNumerator Value="1" />
                <FixedDenominator Value="16" />
                <GridIntervalPixel Value="20" />
                <Ntoles Value="2" />
                <SnapToGrid Value="true" />
                <Fixed Value="false" />
              </ExpressionGrid>
              <Notes>
                <KeyTracks>
                  {key_tracks}
                </KeyTracks>
                <PerNoteEventStore><EventLists /></PerNoteEventStore>
                <NoteIdGenerator NextId="{new_id()}" />
              </Notes>
              <BankSelectCoarse Value="-1" />
              <BankSelectFine Value="-1" />
              <ProgramChange Value="-1" />
              <NoteEditorViewState>
                <IsVisible Value="true" />
                <NoteEditorFoldInZoom Value="-1" />
                <NoteEditorFoldInScroll Value="0" />
                <NoteEditorFoldOutZoom Value="1344" />
                <NoteEditorFoldOutScroll Value="-799" />
                <NoteEditorFoldScaleZoom Value="-1" />
                <NoteEditorFoldScaleScroll Value="0" />
              </NoteEditorViewState>
            </MidiClip>"""


# ─────────────────────────────────────────────────────────────────────────────
# Track builders
# ─────────────────────────────────────────────────────────────────────────────

def _track_header(track_id: int, name: str, color: int) -> str:
    safe = xml_escape(name)
    return f"""  <LomId Value="0" />
  <LomIdView Value="0" />
  <IsContentSelectedInDocument Value="false" />
  <PreferredContentViewMode Value="0" />
  <TrackDelay>
    <Value Value="0" />
    <IsValueSampleBased Value="false" />
  </TrackDelay>
  <Name>
    <EffectiveName Value="{safe}" />
    <UserName Value="" />
    <Annotation Value="" />
    <MemorizedFirstClipName Value="" />
  </Name>
  <Color Value="{color}" />
  <AutomationEnvelopes><Envelopes /></AutomationEnvelopes>
  <TrackGroupId Value="-1" />
  <TrackUnfolded Value="true" />
  <DevicesListWrapper LomId="0" />
  <ClipSlotsListWrapper LomId="0" />
  <ViewData />"""


def _device_chain_open(is_midi: bool = True) -> str:
    """Open a DeviceChain with correct routing stubs."""
    if is_midi:
        return """    <DeviceChain>
      <AutomationLanes><AutomationLanes /></AutomationLanes>
      <ClipEnvelopeChooserViewState><SelectedIndex Value="0" /></ClipEnvelopeChooserViewState>
      <AudioInputRouting>
        <Target Value="AudioIn/None" />
        <UpperDisplayString Value="No Input" />
        <LowerDisplayString Value="" />
      </AudioInputRouting>
      <MidiInputRouting>
        <Target Value="MidiIn/External.All/-1" />
        <UpperDisplayString Value="Ext. In" />
        <LowerDisplayString Value="All Channels" />
      </MidiInputRouting>
      <AudioOutputRouting>
        <Target Value="AudioOut/Master" />
        <UpperDisplayString Value="Master" />
        <LowerDisplayString Value="" />
      </AudioOutputRouting>
      <MidiOutputRouting>
        <Target Value="MidiOut/None" />
        <UpperDisplayString Value="No Output" />
        <LowerDisplayString Value="" />
      </MidiOutputRouting>"""
    else:
        return """    <DeviceChain>
      <AutomationLanes><AutomationLanes /></AutomationLanes>
      <ClipEnvelopeChooserViewState><SelectedIndex Value="0" /></ClipEnvelopeChooserViewState>
      <AudioInputRouting>
        <Target Value="AudioIn/External/0" />
        <UpperDisplayString Value="Ext. In" />
        <LowerDisplayString Value="1" />
      </AudioInputRouting>
      <AudioOutputRouting>
        <Target Value="AudioOut/Master" />
        <UpperDisplayString Value="Master" />
        <LowerDisplayString Value="" />
      </AudioOutputRouting>"""


def midi_track(track_id: int,
               name: str,
               color: int = 0,
               clip_xml: Optional[str] = None,
               volume: float = 1.0,
               pan: float = 0.0,
               num_sends: int = 2) -> str:
    """
    Build a complete <MidiTrack> XML string.

    clip_xml   — output of midi_clip(...), or None for an empty track.
    """
    header = _track_header(track_id, name, color)
    csl    = (_clip_slot_list_with_clip(clip_xml)
              if clip_xml else _empty_clip_slot_list())
    mx     = _mixer(volume, pan, num_sends)
    ms     = _sequencer_block("MainSequencer")
    fs     = _sequencer_block("FreezeSequencer")

    return f"""  <MidiTrack Id="{track_id}">
{header}
{csl}
    <MonitoringEnum Value="1" />
    <CurrentInputRoutingType Value="-1" />
    <CurrentInputSubRoutingType Value="0" />
    <CurrentMonitoringEnum Value="1" />
    <CurrentOutputRoutingType Value="0" />
    <CurrentOutputSubRoutingType Value="0" />
{_device_chain_open(is_midi=True)}
{mx}
{ms}
{fs}
      <Devices />
      <SignalModulations />
    </DeviceChain>
    <SavedPlayingSlot Value="-1" />
    <SavedPlayingOffset Value="0" />
    <Freeze Value="false" />
    <VelocityDetail Value="0" />
    <NeedArrangerRefreeze Value="true" />
    <PostProcessFreezeClips Value="0" />
    <DeviceChainOvertakeEnabled Value="false" />
  </MidiTrack>"""


def audio_track(track_id: int,
                name: str,
                color: int = 0,
                volume: float = 1.0,
                pan: float = 0.0,
                num_sends: int = 2) -> str:
    """Build a complete empty <AudioTrack> XML string."""
    header = _track_header(track_id, name, color)
    csl    = _empty_clip_slot_list()
    mx     = _mixer(volume, pan, num_sends)

    return f"""  <AudioTrack Id="{track_id}">
{header}
{csl}
    <MonitoringEnum Value="1" />
    <CurrentInputRoutingType Value="-1" />
    <CurrentInputSubRoutingType Value="0" />
    <CurrentMonitoringEnum Value="1" />
    <CurrentOutputRoutingType Value="0" />
    <CurrentOutputSubRoutingType Value="0" />
{_device_chain_open(is_midi=False)}
{mx}
      <Devices />
      <SignalModulations />
    </DeviceChain>
    <SavedPlayingSlot Value="-1" />
    <SavedPlayingOffset Value="0" />
    <Freeze Value="false" />
    <NeedArrangerRefreeze Value="true" />
    <PostProcessFreezeClips Value="0" />
    <DeviceChainOvertakeEnabled Value="false" />
  </AudioTrack>"""


def return_track(track_id: int,
                 name: str,
                 color: int = 0,
                 volume: float = 0.75,
                 num_sends: int = 2) -> str:
    """Build a complete <ReturnTrack> XML string."""
    safe = xml_escape(name)
    mx   = _mixer(volume, 0.0, num_sends, is_return=True)

    return f"""  <ReturnTrack Id="{track_id}">
    <LomId Value="0" />
    <LomIdView Value="0" />
    <IsContentSelectedInDocument Value="false" />
    <PreferredContentViewMode Value="0" />
    <TrackDelay>
      <Value Value="0" />
      <IsValueSampleBased Value="false" />
    </TrackDelay>
    <Name>
      <EffectiveName Value="{safe}" />
      <UserName Value="" />
      <Annotation Value="" />
      <MemorizedFirstClipName Value="" />
    </Name>
    <Color Value="{color}" />
    <AutomationEnvelopes><Envelopes /></AutomationEnvelopes>
    <TrackGroupId Value="-1" />
    <TrackUnfolded Value="true" />
    <DevicesListWrapper LomId="0" />
    <ClipSlotsListWrapper LomId="0" />
    <ViewData />
    <DeviceChain>
      <AutomationLanes><AutomationLanes /></AutomationLanes>
      <ClipEnvelopeChooserViewState><SelectedIndex Value="0" /></ClipEnvelopeChooserViewState>
      <AudioInputRouting>
        <Target Value="AudioIn/None" />
        <UpperDisplayString Value="No Input" />
        <LowerDisplayString Value="" />
      </AudioInputRouting>
      <AudioOutputRouting>
        <Target Value="AudioOut/Master" />
        <UpperDisplayString Value="Master" />
        <LowerDisplayString Value="" />
      </AudioOutputRouting>
{mx}
      <Devices />
      <SignalModulations />
    </DeviceChain>
    <Freeze Value="false" />
  </ReturnTrack>"""


def master_track(bpm: float = 138.0,
                 time_sig_num: int = 4,
                 time_sig_den: int = 4) -> str:
    """
    Build the <MasterTrack> block.
    Tempo and time signature live here in Ableton 11.
    """
    return f"""  <MasterTrack>
    <LomId Value="0" />
    <LomIdView Value="0" />
    <IsContentSelectedInDocument Value="false" />
    <PreferredContentViewMode Value="0" />
    <TrackDelay>
      <Value Value="0" />
      <IsValueSampleBased Value="false" />
    </TrackDelay>
    <Name>
      <EffectiveName Value="Master" />
      <UserName Value="" />
      <Annotation Value="" />
      <MemorizedFirstClipName Value="" />
    </Name>
    <Color Value="0" />
    <AutomationEnvelopes><Envelopes /></AutomationEnvelopes>
    <TrackGroupId Value="-1" />
    <TrackUnfolded Value="true" />
    <DevicesListWrapper LomId="0" />
    <ClipSlotsListWrapper LomId="0" />
    <ViewData />
    <DeviceChain>
      <AutomationLanes><AutomationLanes /></AutomationLanes>
      <ClipEnvelopeChooserViewState><SelectedIndex Value="0" /></ClipEnvelopeChooserViewState>
      <AudioOutputRouting>
        <Target Value="AudioOut/None" />
        <UpperDisplayString Value="Ext. Out" />
        <LowerDisplayString Value="1/2" />
      </AudioOutputRouting>
      <Mixer>
        <LomId Value="0" />
        <LomIdView Value="0" />
        <IsExpanded Value="true" />
        <On>
          <LomId Value="0" />
          <Manual Value="true" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </On>
        <ModulationSourceCount Value="0" />
        <ParametersListWrapper LomId="0" />
        <Pointee Id="{new_id()}" />
        <LastSelectedTimeableIndex Value="0" />
        <LastSelectedClipEnvelopeIndex Value="0" />
        <LastSelectedControlEnvelopeIndex Value="0" />
        <Volume>
          <LomId Value="0" />
          <Manual Value="1" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </Volume>
        <Pan>
          <LomId Value="0" />
          <Manual Value="0" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </Pan>
        <SpeakerOn Value="true" />
        <SoloSink Value="false" />
        <PanMode Value="0" />
        <Sends />
        <Cue>
          <LomId Value="0" />
          <Manual Value="0" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </Cue>
        <VolumeModulationTarget Id="{new_id()}" />
        <PanModulationTarget Id="{new_id()}" />
        <MixerSectionExtents />
        <Tempo>
          <LomId Value="0" />
          <Manual Value="{bpm}" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </Tempo>
        <TimeSignature>
          <TimeSignatures>
            <RemoteableTimeSignature Id="0">
              <Numerator Value="{time_sig_num}" />
              <Denominator Value="{time_sig_den}" />
              <Time Value="0" />
            </RemoteableTimeSignature>
          </TimeSignatures>
        </TimeSignature>
        <CrossFade>
          <LomId Value="0" />
          <Manual Value="0.5" />
          <AutomationTarget Id="{new_id()}" />
          <ModulationTarget Id="{new_id()}" />
        </CrossFade>
      </Mixer>
      <Devices />
      <SignalModulations />
    </DeviceChain>
    <Freeze Value="false" />
  </MasterTrack>"""


def scene(index: int, name: str = "", bpm: float = 138.0) -> str:
    safe = xml_escape(name or f"Scene {index + 1}")
    return f"""      <Scene Id="{index}">
        <Name Value="{safe}" />
        <Annotation Value="" />
        <Color Value="-1" />
        <Tempo Value="{bpm}" />
        <IsTempoEnabled Value="false" />
        <TimeSignatureId Value="0" />
        <IsTimeSignatureEnabled Value="false" />
        <LomId Value="0" />
        <ClipSlotsListWrapper LomId="0" />
      </Scene>"""


# ─────────────────────────────────────────────────────────────────────────────
# Top-level LiveSet assembler
# ─────────────────────────────────────────────────────────────────────────────

def assemble_liveset(tracks_xml: str,
                     master_xml: str,
                     scenes_xml: str,
                     bpm: float,
                     root_note: int = 9,   # 9 = A
                     scale_name: str = "Minor",
                     loop_length: float = 32.0) -> str:
    """
    Wrap assembled track XML inside a complete LiveSet + Ableton root element.
    Returns a UTF-8 XML string ready to gzip.
    """
    next_id = _id_counter + 50   # leave headroom

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="11.0_11300" SchemaChangeCount="3" Creator="Ableton Live 11.3.11" Revision="">
  <LiveSet>
    <NextPointeeId Value="{next_id}" />
    <OverwriteProtectionNumber Value="2816" />
    <LomId Value="0" />
    <LomIdView Value="0" />
    <FrameRate Value="2" />
    <Loop>
      <LoopStart Value="0" />
      <LoopEnd Value="{loop_length}" />
      <LoopOn Value="false" />
      <OutMarker Value="{loop_length}" />
      <HiddenLoopStart Value="0" />
      <HiddenLoopEnd Value="{loop_length}" />
    </Loop>
    <SmpteFormat Value="0" />
    <TimeSelection>
      <AnchorTime Value="0" />
      <OtherTime Value="0" />
    </TimeSelection>
    <SequencerNavigator>
      <CurrentTime Value="0" />
      <ScrollerPos Value="0" />
    </SequencerNavigator>
    <ViewStateSessionMixerHeight Value="120" />
    <IsContentSelectedInDocument Value="false" />
    <ScaleMidi Value="false" />
    <CanShowScaleMidi Value="false" />
    <GridIntervalPixel Value="20" />
    <ScaleInformation>
      <RootNote Value="{root_note}" />
      <Name Value="{xml_escape(scale_name)}" />
    </ScaleInformation>
    <InKey Value="true" />
    <SongMasterValues>
      <Volume Value="1" />
      <Pan Value="0" />
    </SongMasterValues>
    <GlobalQuantisation Value="4" />
    <AutoQuantisation Value="0" />
    <AutoColorPickerForPlayerAndGroupTracks Value="true" />
    <ContentSplitterPosition Value="1126" />
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature Id="0">
          <Numerator Value="4" />
          <Denominator Value="4" />
          <Time Value="0" />
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <Tracks>
{tracks_xml}
    </Tracks>
{master_xml}
    <PreHearTrack />
    <SendsPre Value="false" />
    <Scenes>
{scenes_xml}
    </Scenes>
    <Transport>
      <PhaseNudgeTempo Value="10" />
      <LoopOn Value="false" />
      <LoopLength Value="16" />
      <LoopStart Value="0" />
      <DrawMode Value="false" />
      <AutoScrollMode Value="1" />
      <ArrangerOverdub Value="false" />
      <MetronomeTickDuration Value="0.01" />
      <CurrentTime Value="0" />
      <ClipTriggerQuantisation Value="4" />
      <MidiArrangerOverdub Value="false" />
      <ReEnabledSupported Value="true" />
    </Transport>
    <ViewStates>
      <SessionIO Value="0" />
      <SessionSends Value="1" />
      <SessionReturns Value="1" />
      <SessionMixer Value="1" />
      <SessionTrackDelay Value="0" />
      <SessionShowOverView Value="0" />
      <ArrangerIO Value="0" />
      <ArrangerReturns Value="1" />
      <ArrangerMixer Value="1" />
      <ArrangerTrackDelay Value="0" />
      <ArrangerShowOverView Value="0" />
    </ViewStates>
    <GlobalGrooveAmount Value="1.0" />
    <Grid>
      <FixedNumerator Value="1" />
      <FixedDenominator Value="16" />
      <GridIntervalPixel Value="20" />
      <Ntoles Value="2" />
      <SnapToGrid Value="true" />
      <Fixed Value="false" />
    </Grid>
  </LiveSet>
</Ableton>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

# Ableton colour palette (integers Live uses internally)
COLORS = {
    "orange":   4,
    "yellow":   5,
    "teal":     9,
    "blue":    13,
    "purple":  27,
    "green":   22,
    "cyan":    18,
    "red":      1,
    "grey":     0,
    "pink":    26,
    "lime":    14,
}

# Scene labels for a standard trance arrangement
TRANCE_SCENES = [
    "INTRO", "BUILDUP 1", "BREAKDOWN", "DROP 1",
    "BREAK", "BUILDUP 2", "DROP 2", "OUTRO",
]


def build_als(output_path: str = "base_template.als",
              bpm: float = 138.0,
              num_midi_tracks: int = 8,
              num_audio_tracks: int = 2,
              num_returns: int = 2,
              root_note: int = 9,
              scale_name: str = "Minor",
              scene_names: Optional[List[str]] = None) -> str:
    """
    Write a blank Ableton 11 Live Suite template to ``output_path``.

    Parameters
    ----------
    bpm             : project tempo
    num_midi_tracks : how many empty MIDI tracks to create
    num_audio_tracks: how many empty Audio tracks to create
    num_returns     : how many Return tracks (Reverb, Delay, …)
    root_note       : 0=C … 9=A (Ableton's integer encoding)
    scale_name      : scale name string shown in Live's UI
    scene_names     : list of scene label strings (defaults to 8 trance labels)

    Returns the path written.
    """
    reset_ids()

    scenes = scene_names or TRANCE_SCENES
    num_scenes = max(8, len(scenes))

    # Return track names
    return_names = ["Reverb", "Delay", "Chorus", "FX1", "FX2"][:num_returns]

    # ── Build tracks ────────────────────────────────────────────────────────
    track_parts: List[str] = []
    tid = 0

    midi_names = [
        "MIDI 1", "MIDI 2", "MIDI 3", "MIDI 4",
        "MIDI 5", "MIDI 6", "MIDI 7", "MIDI 8",
        "MIDI 9", "MIDI 10",
    ]
    midi_colors = [
        COLORS["orange"], COLORS["yellow"], COLORS["teal"], COLORS["blue"],
        COLORS["purple"], COLORS["green"],  COLORS["cyan"], COLORS["pink"],
        COLORS["lime"],   COLORS["red"],
    ]

    for i in range(num_midi_tracks):
        name  = midi_names[i] if i < len(midi_names) else f"MIDI {i+1}"
        color = midi_colors[i % len(midi_colors)]
        track_parts.append(midi_track(tid, name, color, num_sends=num_returns))
        tid += 1

    audio_colors = [COLORS["lime"], COLORS["grey"]]
    for i in range(num_audio_tracks):
        name  = f"Audio {i+1}"
        color = audio_colors[i % len(audio_colors)]
        track_parts.append(audio_track(tid, name, color, num_sends=num_returns))
        tid += 1

    for i, rname in enumerate(return_names):
        track_parts.append(return_track(100 + i, rname, COLORS["grey"],
                                         num_sends=num_returns))

    # ── Assemble ─────────────────────────────────────────────────────────────
    tracks_xml = "\n".join(track_parts)
    master_xml = master_track(bpm)
    scenes_xml = "\n".join(
        scene(i, scenes[i] if i < len(scenes) else f"Scene {i+1}", bpm)
        for i in range(num_scenes)
    )

    liveset_xml = assemble_liveset(
        tracks_xml, master_xml, scenes_xml,
        bpm=bpm, root_note=root_note, scale_name=scale_name,
    )

    # ── Write ─────────────────────────────────────────────────────────────────
    with gzip.open(output_path, "wb") as f:
        f.write(liveset_xml.encode("utf-8"))

    total_tracks = num_midi_tracks + num_audio_tracks + num_returns
    print(f"[OK]  {output_path}")
    print(f"    {num_midi_tracks} MIDI + {num_audio_tracks} Audio "
          f"+ {num_returns} Returns = {total_tracks} tracks")
    print(f"    BPM {bpm}  |  {num_scenes} scenes  |  {_id_counter} IDs")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Validation helper — call after generation to verify XML integrity
# ─────────────────────────────────────────────────────────────────────────────

def validate_als(path: str) -> bool:
    """
    Parse the gzip+XML and run basic structural checks.
    Returns True if valid, prints errors and returns False otherwise.
    """
    import xml.etree.ElementTree as ET

    try:
        with gzip.open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"[FAIL]  Could not read file: {e}")
        return False

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        print(f"[FAIL]  XML parse error: {e}")
        # Show the offending line
        lines = data.decode("utf-8", errors="replace").splitlines()
        match = re.search(r"line (\d+)", str(e))
        if match:
            ln = int(match.group(1))
            for i in range(max(0, ln - 3), min(len(lines), ln + 2)):
                marker = ">>>" if i + 1 == ln else "   "
                print(f"  {marker} {i+1}: {lines[i]}")
        return False

    errors = []

    # Check root
    if root.tag != "Ableton":
        errors.append(f"Root tag is '{root.tag}', expected 'Ableton'")
    if root.get("MajorVersion") != "5":
        errors.append(f"MajorVersion is '{root.get('MajorVersion')}', expected '5' (Live 11 schema)")

    ls = root.find("LiveSet")
    if ls is None:
        errors.append("Missing <LiveSet>")
        return _report(errors)

    # Required LiveSet children
    for tag in ("Tracks", "MasterTrack", "Scenes", "Transport", "ViewStates"):
        if ls.find(tag) is None:
            errors.append(f"Missing <{tag}> in LiveSet")

    tracks = ls.find("Tracks")
    if tracks is not None:
        for t in tracks:
            name_el = t.find(".//EffectiveName")
            tname   = name_el.get("Value") if name_el is not None else "?"
            if t.find("DeviceChain") is None:
                errors.append(f"Track '{tname}' missing <DeviceChain>")
            if t.find(".//ClipSlotList") is None and t.tag != "ReturnTrack":
                errors.append(f"Track '{tname}' missing <ClipSlotList>")

    # Check for duplicate IDs — only on nodes that must be globally unique.
    # Positional/index Id attrs (ClipSlot, Scene, TrackSendHolder, etc.)
    # legitimately repeat across different parent containers and are skipped.
    GLOBAL_ID_TAGS = {
        "AutomationTarget", "ModulationTarget", "Pointee",
        "MidiClip", "AudioClip", "KeyTrack",
        "MidiTrack", "AudioTrack", "ReturnTrack",
    }
    seen: dict = {}
    for el in root.iter():
        if el.tag in GLOBAL_ID_TAGS and el.get("Id") is not None:
            key = f"{el.tag}:{el.get('Id')}"
            seen[key] = seen.get(key, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        sample = list(dupes.items())[:5]
        errors.append(f"Duplicate global IDs: {sample}")

    return _report(errors)


def _report(errors: list) -> bool:
    if errors:
        for e in errors:
            print(f"  [FAIL]  {e}")
        return False
    print("  [OK]  All structural checks passed")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate an Ableton 11 base template .als")
    p.add_argument("-o", "--output",  default="base_template.als")
    p.add_argument("--bpm",          type=float, default=138.0)
    p.add_argument("--midi-tracks",  type=int,   default=8,
                   dest="midi_tracks")
    p.add_argument("--audio-tracks", type=int,   default=2,
                   dest="audio_tracks")
    p.add_argument("--returns",      type=int,   default=2)
    p.add_argument("--validate",     action="store_true",
                   help="Run structural validation after writing")
    args = p.parse_args()

    path = build_als(
        output_path  = args.output,
        bpm          = args.bpm,
        num_midi_tracks  = args.midi_tracks,
        num_audio_tracks = args.audio_tracks,
        num_returns      = args.returns,
    )

    if args.validate:
        print("\nValidating...")
        ok = validate_als(path)
        sys.exit(0 if ok else 1)
