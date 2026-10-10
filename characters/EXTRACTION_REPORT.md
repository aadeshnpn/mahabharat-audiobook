# Book 1 (Adi Parva) character extraction: report

Generated 2026-10-10; updated 11:40 AM MDT with Aadesh's decisions (see below). Source: KMG translation, clean text in `data/text/book01/001-236.txt`. Output: `characters/book01.json`.

## Method
- **Reading.** The profiles were written by reading the Book 1 text in batches, using per-section digests (`work/digest.txt`) and targeted evidence searches (`work/evidence.py`). No external LLM API was used.
- **Rule: no facts beyond the KMG text.** Every backstory claim carries a § reference.
- **Source files.** Profiles are in `src/mbh/characters/extracted/part1..5.py` and relationships in `extracted/rels.py`.
- **Build.** `build_extracted.py` computes the counts from the text and **validates every citation**. Each section cited in a backstory or relationship must mention the character, by name, alias, or an explicitly listed epithet. The final build has **0 citation problems**; 21 citations rely on an epithet, and these are listed in `epithet_citations`.
- **Fact checks.** `work/factcheck.py` runs targeted keyword checks on 200 specific claims (e.g. "Agni stopped seven times, §225"). All 200 pass. Claims that failed during the work were corrected or removed. For example, I dropped "Maya later asks how he may serve Arjuna", which is not in Book 1.
- **Speech turns.** These count explicit "X said / replied / …," tags plus a quote-anchored pass. That pass credits the first character named in the clause before an opening quote, skipping vocatives ("O Bharata") and objects ("addressed Vayu"). Descriptor speakers ("the deer", "the chief of the fishermen") and the two teachers in §3 have section-specific rules. Treat the counts as a lower bound.
- **Provenance.** Every record has a `provenance` field: `text-extracted`, or `hand` for a voice-only group. Saving from the UI changes it to `text-extracted+hand-edited`.

## Counts
| | |
|---|---|
| Characters | **164** (130 male, 33 female, 1 mixed group) |
| ...with speech | 122 (1,333 speech turns in total) |
| ...flagged `non_speaking` | 42 (kept because they recur in 2+ sections) |
| ...flagged `single_section_speaker` | 21 |
| ...flagged `chorus` (group voices) | 8 |
| Provenance | 163 text-extracted, 1 hand (Devas, heavenly voice) |
| Relationships | **338**, every one with a § reference |
| Citation problems | 0 |
| Speaker tags resolved | 857 of 883 explicit tags (97%) map to an id; 34 generic tags resolved by context, 16 documented as unresolvable |

**Kinds:** human 80, sage 31, deity 17, naga 8, chorus 7, bird 6, celestial 5, asura 5, rakshasa 4, animal 1. The descriptive part is in `kind_detail`, e.g. "Kuru prince; Vasu incarnate".

**Relationship types:**

| Type | Count |
|---|---|
| parent_of | 92 |
| spouse_of | 34 |
| sibling_of | 34 |
| guardian_of | 32 (new) |
| teacher_of | 24 |
| enemy_of | 24 |
| ally_of | 23 |
| cursed | 20 |
| foster_parent_of | 14 |
| rival_of | 13 (new) |
| serves | 11 |
| slew | 7 (new) |
| narrates_to | 6 |
| incarnation_of | 4 (new) |

**Top speakers:**

| Character | Turns |
|---|---|
| Vaisampayana | 369 |
| Sauti | 148 |
| Yayati | 48 |
| Arjuna | 35 |
| Chitraratha (KMG: Angaraparna) | 34 |
| Yudhishthira | 33 |
| Janamejaya | 31 |
| Brahma | 25 |
| Devayani | 25 |
| Kunti | 21 |
| Vyasa | 20 |
| Saunaka | 19 |
| Drona | 19 |
| Ashtaka | 18 |
| Vasishtha | 18 |
| Indra | 17 |
| Sukra | 17 |
| Utanka | 15 |
| Drupada | 15 |
| Ayoda-Dhaumya | 12 |

**Single-section speakers:**
- Frame story and teachers: Veda, Ayoda-Dhaumya, Aruni, Upamanyu, Paushya, Samika
- Yayati's line: Pratardana, Vasumat, Sivi
- Kuru line: Chief of the fishermen (Dasa), Dirghatamas, Mandavya, Kindama, Ekalavya
- Ekachakra: the Brahmana, his wife, his daughter, the Brahmana guest
- Others: Kumbhinasi, Ulupi, Chitravahana

**Group voices:** Rishis of Naimisha, Rishis of Satasringa and Valakhilyas (these three share one voice, `voice_group: naimisha_rishis`), Pitris, Ritwiks and Sadasyas, Aswins, Devas (heavenly voice), Vasus.

## Decisions applied (Aadesh, 2026-10-10)
1. **Display names.** Valadeva now displays as **Balarama**, and Angaraparna as **Chitraratha**. The KMG forms are kept as aliases, and the TTS respelling for Chitraratha now leads with CHIT-ruh-ruh-thuh.
2. **"Krishna" meaning Draupadi** is attributed to **Draupadi** (aliases include *Krishnaa*). The TTS script says "Draupadi" there.
   - `src/mbh/text/krishna.py` resolves **every** bare "Krishna" individually, replacing the old section-level rule. `speakable()` produces the TTS text.
   - Rule chain, first match wins:
     1. hand-reviewed override;
     2. explicit parenthetical ("Krishna (Draupadi)", "Janardana (Krishna)", "Krishna (Dwaipayana)");
     3. Draupadi cue in the clause (maiden, virgin, princess, daughter of Drupada, …);
     4. Vasudeva cue (Vrishni, Valadeva, Madhava, Partha, …);
     5. section default (§186–§210 → Draupadi, else Vasudeva).
   - Result over Book 1: **69 → Draupadi, 124 → Vasudeva, 8 → Vyasa**. I checked all 201 by reading their contexts. 15 that the rules got wrong are hand overrides with a quoted reason (e.g. §223 "Krishna lamented … Dhananjaya pacified her" is Draupadi; §207 "where Krishna is, there victory" is Vasudeva).
   - Per-section lists are in `book01.json` → `name_rules.Krishna`. Draupadi's sections are §1, 2, 61, 62, 63, 167, 171, 186–197, 199–201, 203, 204, 208, 209, 210, 215 and 223.
   - Counts moved accordingly: Draupadi has 7 speech turns (was 5), and Vasudeva has 11 (was 13).
3. **Group rishi voices.** I added the **Rishis of Satasringa** (`satasringa_rishis`, text-extracted). They speak to Pandu in §120, perform the Pandavas' naming rites in §124, and bring the family to Hastinapura in §126. They are no longer an unresolved speaker.
   - A new `voice_group` field makes them and the **Valakhilyas** share the **Rishis of Naimisha** voice. The UI's voice tab shows the shared group voice.
   - The Pitris (ancestors), the Ritwiks (priests) and the Devas keep their own voices. They are not rishi groups.

## Changes vs the provisional starter set (87 characters, 145 relationships)
- **Added: 77.**
  - Frame story and teachers: Veda, Ayoda-Dhaumya, Aruni, Upamanyu, Paushya
  - Bhrigu line: Puloma, Pramadvara, Dundubha
  - Snake stories: Sesha, Elapatra, Samika, Sringin, Krisa, Gaurmukha, Kasyapa the healer, Valakhilyas, Pitris, Ritwiks
  - Gods: Brahma, Vishnu, Mahadeva, Vayu, Varuna, Vrihaspati, Narada, Aswins, Vasus, Tilottama
  - Yayati's line: Yadu, Turvasu, Druhyu, Anu, Pratardana, Vasumat, Sivi
  - Kuru line: Mahabhisha, Chitrangada (Kuru), Dirghatamas, Mandavya, Kuntibhoja, Durvasa, Salya, Kindama, Adhiratha, Radha, Vikarna, Yuyutsu
  - Teachers of the princes: Saradwat, Kripi, Bharadwaja, Kanika, Parasurama
  - Ekachakra: the Brahmana, his wife, his daughter, the Brahmana guest
  - Vasishtha tales: Kumbhinasi, Nandini, Saktri, Adrisyanti, Aurva, Dhaumya
  - Arjuna's travels: Chitravahana, Varga, Abhimanyu
  - Khandava: Sunda, Upasunda, Maya, Aswasena, Mandapala, Jarita, Lapita, Jaritari, Sarisrikka, Stamvamitra, Drona (Sarngaka), Rishis of Naimisha
- **Removed: Amba.** Book 1 has one narrative line about her (§102; §2 only names "the story of Amba" in the Udyoga contents) and no speech.
- **Also dropped during extraction: Duhsala.** She has a single narrative section and no speech.
- **No IDs were renamed,** so all prototype voices carried over: Sauti, Vaisampayana, Bhishma, Santanu, Satyavati, Kunti, Chief of the fishermen, Devas.
- **Display names now follow KMG:**

  | Starter | Now |
  |---|---|
  | Uttanka | Utanka |
  | Balarama | Valadeva |
  | Chitraratha | Angaraparna |
  | Hidimba / Hidimbi | Hidimva (Rakshasa) / Hidimva (Rakshasi) |
  | Jaratkaru (sage) / Jaratkaru (Naga princess) | Jaratkaru (Rishi) / Jaratkaru (Naga woman) |
  | Dasa (fisherman chief) | Chief of the fishermen |
- **Rewritten from the text:** 86 of 87 roles and backstories (with §), 46 voice briefs, and 58 alias lists.
- **Speech counts rose sharply** under the new attribution (the starter counts were the undercount). Examples:

  | Character | Starter | Now |
  |---|---|---|
  | Yudhishthira | 7 | 33 |
  | Arjuna | 11 | 35 |
  | Drona | 5 | 19 |
  | Drupada | 3 | 15 |
  | Bhishma | 2 | 10 |
  | Bhima | 2 | 10 |
- **Starter `unmapped_speakers`** (150 raw tag counts, backed up in `backups/`) is replaced by `book01_unmapped_speakers.json`, which lists the 33 resolved and 17 documented-unresolved tags.

## Unresolved speakers (documented, not given voices)
| Tag | What it is |
|---|---|
| §3 "He", "his mother" | Sarameya and Sarama (dogs), one line each |
| §18 "the Ocean" | the Ocean personified, one line |
| §22 "They" | Kadru's sons, one line |
| §37, §190 "Others" | crowds |
| §63 "They" | the fishermen, one line |
| §104 "She", "Vali" | Mamata and King Vali, one section each |
| §167 "The Pandavas" | group line (read by Yudhishthira or the narrator) |
| §186 "The Brahmanas" | travelling Brahmanas (crowd) |
| §209 "Some" | citizens (crowd) |
| §215, §219 "The Brahmana" | one-off Brahmanas |
| §12 "Thus", §39 "Well" | not speakers |

## Open decisions for Aadesh
1. ~~Display names~~: done (Balarama, Chitraratha).
2. ~~Krishna/Draupadi~~: done, resolved per occurrence. The Hidimva and Jaratkaru splits are still pronoun heuristics, so their counts are approximate.
3. **Gods' mention counts are inflated** by similes ("like Indra") and by place names (the river Ganga). Use speech turns, not mentions, to rank them.
4. **§176 is missing from the source** (it duplicates §177) and was skipped.
5. ~~Rishi group voices~~: done (Naimisha voice shared by Satasringa and the Valakhilyas). Crowd lines such as the citizens (§209) and the travelling Brahmanas (§186) remain narrator/generic. Should they get a generic crowd voice?
6. **42 recurring non-speaking characters** (e.g. Nakula, Sahadeva, Sakuni, Aswatthaman, Abhimanyu) need no voice in Book 1. Should we design their voices now, for later books?
7. **TTS choice for Draupadi-"Krishna":** "Draupadi" (current) or "Krishnaa". Change `TTS_DRAUPADI` in `mbh/text/krishna.py` to switch.

## Files and backups
- `characters/backups/book01.starter.20261010_104311.json`: the old seed file.
- `characters/backups/db_export.before_extraction.20261010_104311.json`, plus one `db_export.before_reseed.*.json` per re-seed: DB exports.
- `db_export.bad_kind_baseline_intermediate.20261010_111830.json`: kept for the record only. It comes from a re-seed run with the wrong baseline; that run was undone.
- `db_export.before_reseed.20261010_113653.json`: the export taken before applying the decisions.
- `characters/backups/last_seed.json`: the baseline used by `mbh.webapp.reseed` to detect UI edits.

## Time
The build and validation run takes about 4 s. The write, verify and re-seed phase ran from about 10:43 to 11:18 AM MDT. The earlier reading and profile-writing time was not measured separately.
