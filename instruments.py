"""Shared instrument guidance for the picker, routine, reset, and AI brief."""

FAMILIES = {
    "brass": {
        "warmup": "Start with easy sustained notes in a comfortable range, then a familiar slow pattern. Keep the sound relaxed.",
        "entrance": "Isolate one entrance. Hear the starting pitch, breathe with the pulse, and try three comfortable starts before adding the next note.",
        "terms": "air, articulation, comfortable register",
    },
    "woodwind": {
        "warmup": "Start with easy sustained notes, then a familiar slow fingering pattern. Listen for an even sound through the changes.",
        "entrance": "Isolate one entrance. Set the fingering first, breathe with the pulse, and try three clear starts before adding the next note.",
        "terms": "air, articulation, finger coordination",
    },
    "bowed strings": {
        "warmup": "Start with comfortable open-string bow strokes, then a familiar slow pattern. Listen for an even sound at each bow change.",
        "entrance": "Isolate one entrance. Prepare the bow and left-hand position before the beat. Try three even starts, then add the next note.",
        "terms": "bow changes, string crossings, left-hand placement",
    },
    "keyboard": {
        "warmup": "Start with a familiar slow pattern in a comfortable hand position. Listen for even timing and volume without forcing speed.",
        "entrance": "Isolate one entrance. Set the hand position before the beat. Try it with each hand separately, then together if the passage uses both hands.",
        "terms": "hand coordination, fingering, even touch",
    },
    "plucked strings": {
        "warmup": "Start with a familiar slow picking or plucking pattern. Keep the hands relaxed and listen for an even attack.",
        "entrance": "Isolate one entrance. Prepare both hands before the beat. Try three clean plucks or strums with the click, then add the next note or chord.",
        "terms": "picking or plucking, fretting, string changes",
    },
    "percussion": {
        "warmup": "Start with a familiar slow sticking pattern on your usual practice surface. Listen for even spacing and volume.",
        "entrance": "Isolate the first stroke or small rhythmic group. Prepare before the beat and repeat it three times with even spacing, then add the next group.",
        "terms": "sticking, rebound, stroke consistency",
    },
    "voice": {
        "warmup": "Start with a familiar gentle vocal warm-up in a comfortable range. Keep it easy and stop if it feels strained.",
        "entrance": "Isolate the first sung note or syllable. Hear the starting pitch and breathe before the beat. Try three comfortable starts, then add the next syllable.",
        "terms": "breath, vowel, diction, comfortable range",
    },
    "other": {
        "warmup": "Use a familiar, comfortable warm-up for your instrument. Start slowly and focus on even timing.",
        "entrance": "Isolate the beginning of the passage. Prepare before the beat, try three consistent starts with the click, then add the next small group.",
        "terms": "timing, phrasing, listening, small sections",
    },
}

# Exact aliases avoid guessing an instrument from a substring (e.g. bass).
INSTRUMENTS = [
    ("French horn", "brass", ["horn", "frenchhorn"], "valve coordination"),
    ("Trumpet", "brass", ["cornet"], "valve coordination"),
    ("Trombone", "brass", [], "slide coordination; do not prescribe valve exercises"),
    ("Euphonium", "brass", ["baritone horn"], "valve coordination"),
    ("Tuba", "brass", [], "valve coordination"),
    ("Flute", "woodwind", [], "air and finger coordination; no reed exercises"),
    ("Piccolo", "woodwind", [], "air and finger coordination; no reed exercises"),
    ("Clarinet", "woodwind", ["bb clarinet", "b-flat clarinet"], "single reed, register changes"),
    ("Bass clarinet", "woodwind", [], "single reed, register changes"),
    ("Oboe", "woodwind", [], "double reed, finger coordination"),
    ("Bassoon", "woodwind", [], "double reed, finger coordination"),
    ("Soprano saxophone", "woodwind", ["soprano sax"], "single reed, finger coordination"),
    ("Alto saxophone", "woodwind", ["alto sax"], "single reed, finger coordination"),
    ("Tenor saxophone", "woodwind", ["tenor sax"], "single reed, finger coordination"),
    ("Baritone saxophone", "woodwind", ["baritone sax", "bari sax"], "single reed, finger coordination"),
    ("Violin", "bowed strings", [], "bow and left-hand coordination"),
    ("Viola", "bowed strings", [], "bow and left-hand coordination"),
    ("Cello", "bowed strings", ["violoncello"], "bow and left-hand coordination"),
    ("Double bass", "bowed strings", ["upright bass", "string bass"], "bowed or pizzicato; ask which applies"),
    ("Piano", "keyboard", [], "hand coordination, touch"),
    ("Guitar", "plucked strings", ["acoustic guitar", "electric guitar"], "picking, strumming, chord changes"),
    ("Bass guitar", "plucked strings", ["electric bass"], "plucking, fretting, string changes"),
    ("Percussion", "percussion", ["drums", "snare drum", "drum kit"], "ask which percussion instrument before pitched exercises"),
    ("Voice", "voice", ["vocals", "singing"], "vowels and diction; no instrumental fingerings"),
]


def instrument_guidance(name):
    normalized = " ".join(str(name).casefold().split())
    for label, family, aliases, specific in INSTRUMENTS:
        if normalized in [label.casefold(), *aliases]:
            return dict(name=label, family=family, specific=specific, **FAMILIES[family])
    return dict(name=str(name), family="other", specific="Unknown technique: keep suggestions instrument-neutral.", **FAMILIES["other"])
