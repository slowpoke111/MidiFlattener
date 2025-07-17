import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from enum import Enum
import argparse
import os


class Strategy(Enum):
    BALANCED = 'balanced'
    DROP_EXCESS = 'drop_excess'
    FIRST_FIT = 'first_fit'


def splitPartIntoVoices(notes, maxVoices=8, strategy=Strategy.BALANCED):

    voices = [[] for _ in range(maxVoices)]

    for note in notes:
        placed = False
        startTime = note[0]
        endTime = note[1]
        
        if strategy == Strategy.BALANCED:
            availableVoices = []
            for i, voice in enumerate(voices):
                if not voice or startTime >= voice[-1][1]:  
                    availableVoices.append(i)
            
            if availableVoices:
                bestVoiceIdx = min(availableVoices, key=lambda i: len(voices[i]))
                voices[bestVoiceIdx].append(note)
                placed = True
        
        elif strategy == Strategy.DROP_EXCESS:
            for voice in voices:
                if not voice or startTime >= voice[-1][1]:
                    voice.append(note)
                    placed = True
                    break
            placed = True  
        
        else: # strategy == Strategy.FIRST_FIT 
            for voice in voices:
                if not voice or startTime >= voice[-1][1]:
                    voice.append(note)
                    placed = True
                    break
        
        if not placed:
            if strategy == Strategy.DROP_EXCESS:
                continue  
            else:
                raise Exception(f"More than {maxVoices} simultaneous notes detected! Consider using strategy=Strategy.DROP_EXCESS (Arg: -s drop_excess) or increasing maxVoices.")
    
    return voices

def extractMetaMessages(tracks):
    metaEvents = []
    
    for trackIndex, track in enumerate(tracks):
        currentTime = 0
        for msg in track:
            currentTime += msg.time
            if msg.is_meta:
                metaEvents.append((currentTime, msg.copy()))
    
    metaEvents.sort(key=lambda x: x[0])
    return metaEvents

def createMetaTrack(metaEvents):
    track = MidiTrack()
    currentTime = 0
    
    for eventTime, metaMsg in metaEvents:
        deltaTime = eventTime - currentTime
        metaMsg.time = deltaTime
        track.append(metaMsg)
        currentTime = eventTime
    
    return track

def parseMidiNotes(track):

    notes = []
    ongoing = {} 

    currentTime = 0
    for msg in track:
        currentTime += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            ongoing[msg.note] = (currentTime, msg.velocity)
        elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in ongoing:
                start, velocity = ongoing.pop(msg.note)
                notes.append((start, currentTime, msg.note, velocity))

    notes.sort(key=lambda x: x[0])
    return notes

def createVoiceTrack(voiceNotes, channel, ticksPerBeat):

    track = MidiTrack()
    currentTime = 0
    for start, end, note, velocity in voiceNotes:
        deltaStart = start - currentTime
        track.append(Message('note_on', note=note, velocity=velocity, time=deltaStart, channel=channel))
        deltaEnd = end - start
        track.append(Message('note_off', note=note, velocity=0, time=deltaEnd, channel=channel))
        currentTime = end
    return track

def analyzeAndPrintTrackInfo(mid):

    allNotes = []  
    
    for i, track in enumerate(mid.tracks):
        notes = parseMidiNotes(track)
        print(f'Track {i}: {len(notes)} total notes')
        allNotes.extend(notes)  
    
    maxSimultaneous = 0
    if allNotes:
        events = []
        for start, end, note, velocity in allNotes:
            events.append((start, 'start'))
            events.append((end, 'end'))
        
        events.sort(key=lambda x: (x[0], x[1] == 'start'))
        
        currentActive = 0
        
        for time, eventType in events:
            if eventType == 'start':
                currentActive += 1
                maxSimultaneous = max(maxSimultaneous, currentActive)
            else:  
                currentActive -= 1
        
        print(f'\nMaximum simultaneous notes across all tracks: {maxSimultaneous}')
    else:
        print('\nNo notes found in any track')
    print()
    
    return maxSimultaneous

def splitMidiPolyphonyToVoices(inputFile, outputFile, maxVoices=8, strategy=Strategy.BALANCED, autoOptimizeVoices=True):
    mid = MidiFile(inputFile)
    ticksPerBeat = mid.ticks_per_beat
    newMid = MidiFile()
    newMid.ticks_per_beat = ticksPerBeat
    
    print("\n--- Input MIDI Analysis ---")
    maxSimultaneous = analyzeAndPrintTrackInfo(mid)
    
    if autoOptimizeVoices and maxSimultaneous > 0:
        optimalVoices = min(maxSimultaneous, maxVoices)
        print(f"Auto-optimizing: Using {optimalVoices} voices (max simultaneous: {maxSimultaneous}, max allowed: {maxVoices})")
        maxVoices = optimalVoices
    
    print("Extracting meta messages (tempo, time signature, etc.)...")
    metaEvents = extractMetaMessages(mid.tracks)
    print(f"Found {len(metaEvents)} meta events to preserve")
    
    if metaEvents:
        metaTrack = createMetaTrack(metaEvents)
        metaTrack.name = "Meta Track"
        newMid.tracks.append(metaTrack)
    
    allNotes = []
    for i, track in enumerate(mid.tracks):
        notes = parseMidiNotes(track)
        if notes:  
            trackNotes = [(start, end, note, velocity, i) for start, end, note, velocity in notes]
            allNotes.extend(trackNotes)
    
    if not allNotes:
        print("No notes found in any track.")
        newMid.save(outputFile)
        return
    
    allNotes.sort(key=lambda x: x[0])
    
    print(f"Processing {len(allNotes)} total notes across all tracks into {maxVoices} voices")
    
    voices = splitPartIntoVoices(allNotes, maxVoices=maxVoices, strategy=strategy)
    
    channelCounter = 0
    for voiceIndex, voiceNotes in enumerate(voices):
        if not voiceNotes:
            continue
        
        while channelCounter == 9:  # skip percussion channel
            channelCounter += 1
        channel = channelCounter % 16
        channelCounter += 1
        
        voiceNotesClean = [(start, end, note, velocity) for start, end, note, velocity, _ in voiceNotes]
        
        voiceTrack = createVoiceTrack(voiceNotesClean, channel, ticksPerBeat)
        voiceTrack.name = f"Voice{voiceIndex}"
        newMid.tracks.append(voiceTrack)

    print("\n--- Output MIDI Analysis ---")
    analyzeAndPrintTrackInfo(newMid)
    
    newMid.save(outputFile)
    print(f"Saved split MIDI to {outputFile}")

def main():
    parser = argparse.ArgumentParser(
        description='Split polyphonic MIDI files into separate voice tracks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python flattenMIDI.py input.mid --max-voices 4
  python flattenMIDI.py input.mid -v 8 --output output.mid
  python flattenMIDI.py input.mid -v 6 --strategy drop_excess --no-auto-optimize

Strategies:
  balanced     - Distribute notes evenly across voices (default)
  drop_excess  - Drop notes that exceed the voice limit
  first_fit    - Assign notes to the first available voice
        """
    )
    
    parser.add_argument('input_file', 
                       help='Input MIDI file path')
    
    parser.add_argument('-v', '--max-voices', 
                       type=int, 
                       required=True,
                       help='Maximum number of voices/tracks to create (required)')
    
    parser.add_argument('-o', '--output', 
                       help='Output MIDI file path (default: {input_filename}_Flattened.mid)')
    
    parser.add_argument('-s', '--strategy', 
                       choices=['balanced', 'drop_excess', 'first_fit'],
                       default='first_fit',
                       help='Voice assignment strategy (default: first_fit)')
    
    parser.add_argument('--no-auto-optimize', 
                       action='store_true',
                       help='Disable automatic voice optimization based on simultaneous notes, and use the specified maxVoices directly')
    
    args = parser.parse_args()
    
    if args.output is None:
        input_path = os.path.splitext(args.input_file)[0]
        args.output = f"{input_path}_Flattened.mid"
    
    strategy_map = {
        'balanced': Strategy.BALANCED,
        'drop_excess': Strategy.DROP_EXCESS,
        'first_fit': Strategy.FIRST_FIT
    }
    strategy_enum = strategy_map[args.strategy]
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        return 1
    
    try:
        splitMidiPolyphonyToVoices(
            inputFile=args.input_file,
            outputFile=args.output,
            maxVoices=args.max_voices,
            strategy=strategy_enum,
            autoOptimizeVoices=not args.no_auto_optimize
        )
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())