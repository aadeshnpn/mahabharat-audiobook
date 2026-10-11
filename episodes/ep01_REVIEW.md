# Episode 1 draft: review notes (text only, no audio yet)

Script for review: `episodes/ep01_script.md` (line-by-line, with the TTS text where it differs). Cue sheet: `episodes/ep01.cues.txt`.

## Assumption to confirm
**The pilot is treated as a standalone trailer, so Episode 1 starts again from Book 1 §1 ¶1** (the invocation and Sauti's arrival, which the pilot also covers). If you'd rather the pilot *be* the start of the run, drop the `opening` segment (¶1–5) and start at ¶6. That frees about 4 minutes, so the end moves to ¶22 (the tree of Yudhishthira, about 16:40) or later.

## Span and end point
- **Book 1 §1 ¶1–17, unabridged KMG, in order. Estimated 17:22** (1042 s at 138.1 wpm, pauses included; 83 lines).
- **Ends at ¶17**, the close of Sauti's first long discourse. His quotation opens at ¶6 and closes here, on the image of the Bharata as an inexhaustible tree. That's a narration boundary, not mid-dialogue. The next paragraph opens "I will now speak of the undying flowery and fruitful productions of this tree…" and turns to the first people of the story (Vyasa fathering Dhritarashtra, Pandu and Vidura), which makes a natural opener for Episode 2.

Alternative end points (from `mbh episode breaks`, estimates include pauses):

| End | Time | What happens there |
|---|---|---|
| ¶15 | ~15:24 | The Ganesa scene ends: Ganesa pauses to ponder the knotted verses while Vyasa composes on. The most story-like ending, with a light smile as the hook. |
| **¶17** | **~17:22** | **The tree of the Bharata (chosen).** |
| ¶18 | ~18:02 | Vyasa fathers Dhritarashtra, Pandu and Vidura, then returns to his retreat. The first human story beat, but it ends inside Sauti's next discourse. |
| ¶21 | ~20:23 | "Know that I, Sauti, have also repeated one hundred thousand verses." Over the 20-minute cap, and it ends on numbers. |
| ¶22 | ~20:41 | "Yudhishthira is a vast tree…" Over the cap, and this edition has no matching "Duryodhana is a tree of passion" line, so it would end on half a contrast. |

## Outline
1. **Sauti arrives at Naimisha (¶1–5, ~4:03).** Invocation ("Om!"). Ugrasrava (Sauti), the bard, arrives at Saunaka's twelve-year sacrifice in the Naimisha forest. The ascetics greet him and ask where he has come from. He tells them he has heard Vyasa's stories at Janamejaya's snake sacrifice and visited Samantapanchaka, the old battlefield of the Kurus and Pandavas, and asks what they want to hear. The Rishis ask for the Bharata.
2. **Invocation and the creation (¶6–10, ~5:56).** Sauti bows to Isana, Brahma, Vishnu and Hari. In the darkness before creation a mighty egg (Mahadivya) appears. From it come Brahma, the Prajapatis, the gods and every class of being, the elements and the seasons. Everything is destroyed and renewed in the endless wheel of the Yugas. The generations of the Devas follow, down to the houses of the Kurus, Yadus and Bharata, and then the many ways the learned read the Bharata.
3. **Vyasa, Brahma and Ganesa (¶11–15, ~5:24).** Vyasa has finished his poem but has no one to write it down. Brahma comes in person and blesses the work ("Thou hast called thy present work a poem, wherefore it shall be a poem"). Brahma tells him to think of Ganesa. Ganesa agrees on one condition: his pen must never stop. Vyasa counters that Ganesa must understand every verse before writing it, then knots the verses so tightly that even Ganesa has to pause, which buys him time to compose.
4. **The tree of the Bharata (¶16–17, ~1:55).** The work is collyrium, sun, moon and lamp against ignorance. Then the whole poem as a tree: the chapter of contents is the seed, Pauloma and Astika the root, Sambhava the trunk… "a source of livelihood to all distinguished poets."

## List-like passages: an honest evaluation and options
Inside this cut, the list-heavy stretches are:

| ¶ | Passage | Length |
|---|---|---|
| ¶6 | Litany of divine attributes | ~1.4 min |
| ¶7 | Prajapatis and classes of beings, roughly the second half of the paragraph | ~1.6 min |
| ¶9 | Generations of the Devas: "thirty-three thousand, thirty-three hundred and thirty-three", nine sons of Div, the jyoti lineage | ~1.35 min |
| ¶11 | Vyasa's catalogue of the poem's subjects | ~1.4 of 2.75 min |
| ¶17 | The Parvas as parts of a tree | ~1.1 min |

That's about 5–6 minutes of 17, but each stretch is short and sits between story beats. As audio:
- **¶6, ¶7 and ¶17** read as ritual and cosmological litany. With Sauti's measured voice and the cues (celestial for the egg, the grave drone for the wheel of the Yugas, the building tree ending), they carry well.
- **¶11's catalogue** sits inside a scene, Vyasa pleading his case to Brahma, which keeps it anchored.
- **¶9 is the weak spot:** numbers plus a string of nine unfamiliar names with no story. Listeners are most likely to drift here.

Options:
1. **Keep everything unabridged (recommended for Episode 1, and applied).** It's the opening; the litany texture is part of its character, and it stays within the target length.
2. **Marked abridgement of ¶9** (and optionally ¶11's catalogue). Saves about 1.4–2.8 min (to ~14.6–16 min) and is flagged `abridged` in the script. This needs a small "drop sentences" override, which doesn't exist yet.
3. **A narrator summary bridge for ¶9, flagged non-KMG.** For example: "Sauti then traced the generations of the gods, from the sons of Div down to the houses of the Kurus, the Yadus and Bharata." That's about 10 s instead of about 80 s.

Looking ahead, abridgement will really be needed in **§2, the Parva-sangraha** (about 62 minutes, largely a list of the hundred parvas and their verse counts); options 2 or 3 will be needed there. The rest of §1 (¶23–¶40, Dhritarashtra's "When I heard…" lament to Sanjaya, about 25 minutes) is dramatic and should play well unabridged.

## Attribution fixes applied (episodes/overrides/ep01.json)
- ¶13: Vyasa's request to Ganesa was inside Sauti's narration, and was also split at "Ganas!". It's now merged, then split into a Sauti narration line and a Vyasa speech line.
- ¶14: Ganesa's condition and Vyasa's counter-condition were one Sauti line. They're now split into Ganesa / Sauti ("And Vyasa said unto that divinity,") / Vyasa.
- ¶14: "by repeating the word Om! proceeded to write" had been split mid-sentence at "Om!". It's now merged, with the TTS reading "the word Om, proceeded…".
- A few emotion and direction notes: Vyasa pleading for a writer, Brahma solemn and then commanding, Ganesa playful.
- The `split` override only applies if its parts re-join exactly to the original KMG wording.

## Names (pronunciation)
- 31 names in this episode were already verified in the pilot.
- **89 newer names were tested in a harness round** (Sauti's voice, carrier sentence, ASR plus a sound-key check). 83 pass with the KMG spelling. Four needed a plain-word form: Guhyakas → "Goohyakas", Mahya → "Mahhya", Sambhava → "Sumbhuvuh", Aswamedha → "Ushvumaydhuh". Asavaha and Vishnu passed with the KMG spelling on a retake.
- **Pending: Prachetas, Pitris.** No form passed. The ASR heard "Prasheta" and "Petrie", likely just dropping the plural "s". They keep the KMG spelling, and are worth a listen at render time.
- These passes are **provisional** (one voice, one take) and are marked that way in `lexicon/book01.tsv` (`verified` = 0, with a harness note). The pilot's bar was 2+ voices. They're narrated by Sauti, the voice that was tested.
- Still pending from the pilot: **Sauti** itself (ASR heard "sortie" / "Sati").

## Voices
- Have refs: Sauti (66 lines), Rishis of Naimisha (6).
- **Need a voice:**
  - **Vyasa** (5 lines; in the character registry, no ref yet).
  - **Brahma** (5 lines; in the registry, no ref).
  - **Ganesa** (1 line). Not in the character registry, because he only speaks in §1 and the extraction kept recurring characters. Add him as an important single-section speaker, then design a voice.
