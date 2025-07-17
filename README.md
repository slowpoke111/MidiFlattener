# MidiFlattener
For use with [LSRobotics/2025Robot](https://github.com/LSRobotics/2025Robot)

Split a polyphonic midi file into a midi file with seperate monophonic voices, for control over how CTRE Orchestrate slices it.

usage: flattenMIDI.py [-h] -v MAX_VOICES [-o OUTPUT] [-s {balanced,drop_excess,first_fit}] [--no-auto-optimize] input_file

Split polyphonic MIDI files into separate voice tracks

positional arguments:
  input_file            Input MIDI file path

options:
  -h, --help            show this help message and exit
  -v, --max-voices MAX_VOICES
                        Maximum number of voices/tracks to create (required)
  -o, --output OUTPUT   Output MIDI file path (default: {input_filename}_Flattened.mid)
  -s, --strategy {balanced,drop_excess,first_fit}
                        Voice assignment strategy (default: first_fit)
  --no-auto-optimize    Disable automatic voice optimization based on simultaneous notes, and use the specified maxVoices directly

Examples:
  python flattenMIDI.py input.mid --max-voices 4
  python flattenMIDI.py input.mid -v 8 --output output.mid
  python flattenMIDI.py input.mid -v 6 --strategy drop_excess --no-auto-optimize

Strategies:
  balanced     - Distribute notes evenly across voices (default)
  drop_excess  - Drop notes that exceed the voice limit
  first_fit    - Assign notes to the first available voice
