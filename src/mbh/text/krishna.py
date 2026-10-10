"""Resolve each bare 'Krishna' in the KMG Book 1 text to Vasudeva ('krishna'), Draupadi or Vyasa.

KMG uses 'Krishna' for Vasudeva, for Draupadi (Krishnaa, 'the dark one') and occasionally for Vyasa
(Krishna-Dwaipayana). Decision (Aadesh, 2026-10-10): where it means Draupadi, attribute it to Draupadi and
the TTS script says 'Draupadi' (TTS_DRAUPADI; 'Krishnaa' is the alternative).

Rule chain per occurrence (first match wins):
  0. hand-reviewed override (OVERRIDES, keyed by section and occurrence index);
  1. explicit parenthetical / epithet right next to the word ('Krishna (Draupadi)', 'Janardana (Krishna)', 'Krishna (Vyasa)');
  2. Draupadi cue within the clause window (maiden, virgin, princess, daughter of Drupada, ...);
  3. Vasudeva cue within the clause window (Vrishni, Yadava, Valadeva, Madhava, Kesava, Janardana, ...);
  4. section default: §186–§210 (Draupadi's swayamvara and marriage) -> Draupadi, otherwise Vasudeva.
resolve(s, text) -> [(start, end, who, rule)]; speakable(s, text) -> text with Draupadi-'Krishna' replaced.
"""
import re

TTS_DRAUPADI = "Draupadi"
_BARE = re.compile(r"\bKrishna\b(?![- ]Dwaipayana)")
PAREN_D = re.compile(r"^\s*\((?:Draupadi|the princess|Panchali)")
PAREN_V = re.compile(r"^\s*\((?:Vyasa|Dwaipayana|the dark)")
BEFORE_V = re.compile(r"(?:his grandfather|son of Satyavati)\s*$")
BEFORE_K = re.compile(r"(?:Vasudeva|Kesava|Janardana|Govinda|Madhava|Damodara|Hari|Kesava's self,)\s*\(?\s*$")
D_CUE = re.compile(r"\b(maiden|virgin|princess|Princess|daughter of Drupada|Drupada's daughter|Yajnaseni|Panchali|of celestial beauty|"
                   r"faultless|chaste|sprung from Prishata|connubial|birth of Krishna|births of Krishna|"
                   r"shall be mine|obtaining Krishna|set on Krishna|contemplation of Krishna|attired in red)\b")
K_CUE = re.compile(r"\b(Vrishni|Yadu|Yadava|Dasarha|Valadeva|Baladeva|Balarama|Halayudha|Rama|Madhava|Kesava|Vasudeva|Janardana|"
                   r"Damodara|Govinda|Hari|Narayana|Nara|Satyaki|charioteer|counsellor|counsels|Dwaravati|Dwaraka|Subhadra|"
                   r"Partha|Vibhatsu|Jishnu|Dhananjaya|Arjuna|Aswatthaman|Bhishma|Karna|Duryodhana|Gandhari|Yoga|universe)\b")
# hand-reviewed residue: (section, n-th bare 'Krishna' in that section, 0-based) -> who
OVERRIDES = {   # each checked against the text by hand (2026-10-10)
    (167, 1): "draupadi",  # 'the extraordinary birth of Krishna ... from the centre of the sacrificial platform'
    (190, 0): "krishna",   # Arjuna 'remembering Krishna also, he took it [the bow] up'
    (190, 1): "draupadi",  # 'Krishna beholding the mark shot ... approached the son of Kunti with a white robe and a garland'
    (192, 1): "krishna",   # 'Krishna, having beheld that feat of Bhima ... induced them [the kings] to abandon the fight'
    (197, 2): "draupadi",  # 'Then Kunti and Krishna and Bhima and Arjuna and the twins'
    (201, 3): "krishna",   # 'And Krishna also gave them female servants' (continues Hari's wedding gifts)
    (204, 3): "krishna",   # Karna: 'there is nothing that Krishna may not sacrifice for the sake of the Pandavas'
    (207, 1): "krishna", (207, 2): "krishna",   # 'where Krishna is, there victory also must be'
    (209, 2): "krishna",   # 'the Pandavas ... and Krishna and Vidura, taking with them Krishna, the daughter of Drupada' (first one)
    (209, 4): "krishna",   # 'the Pandavas, with Krishna at their head' (Vasudeva settles them at Khandavaprastha)
    (215, 0): "draupadi", (215, 1): "draupadi",  # 'Krishna became obedient unto all the five sons'; 'occupied by Yudhishthira ... with Krishna'
    (223, 0): "draupadi",  # 'And Krishna lamented much in this strain. But Dhananjaya pacified her'
    (223, 1): "draupadi",  # 'Krishna rose hastily and embraced the sister of Madhava'
}

def _clause(t, a, b):
    lo = max(t.rfind(x, 0, a) for x in (". ", "; ", "! ", "? ", "' ", "\" ")) + 1
    his = [i for i in (t.find(x, b) for x in (". ", "; ", "! ", "? ")) if i != -1]
    hi = min(his) if his else len(t)
    return t[max(lo, a - 140):min(hi, b + 120)]

def resolve(s, t):
    out = []
    for i, m in enumerate(_BARE.finditer(t)):
        a, b = m.span(); before, after = t[max(0, a - 40):a], t[b:b + 30]; cl = _clause(t, a, b)
        if (s, i) in OVERRIDES: who, rule = OVERRIDES[(s, i)], "override"
        elif PAREN_D.search(after): who, rule = "draupadi", "parenthetical"
        elif PAREN_V.search(after) or BEFORE_V.search(before): who, rule = "vyasa", "parenthetical"
        elif BEFORE_K.search(before) or re.match(r"^\s*(?:and Balarama|and Valadeva|and Arjuna|and Partha)", after): who, rule = "krishna", "parenthetical"
        elif D_CUE.search(cl): who, rule = "draupadi", "draupadi-cue"
        elif K_CUE.search(cl): who, rule = "krishna", "vasudeva-cue"
        else: who, rule = ("draupadi" if 186 <= s <= 210 else "krishna"), "section-default"
        out.append((a, b, who, rule))
    return out

def speakable(s, t):
    parts, last = [], 0
    for a, b, who, _ in resolve(s, t):
        parts.append(t[last:a]); parts.append(TTS_DRAUPADI if who == "draupadi" else t[a:b]); last = b
    parts.append(t[last:]); return "".join(parts)
