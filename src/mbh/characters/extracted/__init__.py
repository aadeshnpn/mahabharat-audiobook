"""Text-grounded Book 1 (Adi Parva) character profiles, extracted by reading the KMG text.
Each profile: C(id, name, aliases, respelling, gender, kind, era_age, role, backstory, personality, emotions, voice_brief,
key_sections, flags). Lists are '|'-separated strings. Section refs (§N) point at data/text/book01/NNN.txt.
Relationships: (source, type, target, section, note)."""
CHARS, RELS = [], []
def C(id, name, aliases, respelling, gender, kind, era_age, role, backstory, personality, emotions, voice_brief,
      key_sections, flags="", provenance="text-extracted", voice_group=""):
    sp = lambda s: [x.strip() for x in s.split("|") if x.strip()] if isinstance(s, str) else list(s)
    CHARS.append(dict(id=id, name=name, aliases=sp(aliases), respelling=respelling, gender=gender, kind=kind,
        era_age=era_age, role=role, backstory=backstory, personality=sp(personality), emotional_range=sp(emotions),
        voice_brief=voice_brief, key_sections=[int(x) for x in str(key_sections).replace(",", " ").split()],
        flags=sp(flags), provenance=provenance, voice_group=voice_group))
def R(*rows):
    for r in rows: RELS.append(dict(source=r[0], type=r[1], target=r[2], section=r[3], note=r[4] if len(r) > 4 else ""))
from . import part1, part2, part3, part4, part5, rels  # noqa
