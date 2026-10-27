# Episode 6 v1: render QA (2026-10-27)

**Render:** 115 lines in 5 shards (`tools/render_sharded.sh episodes/ep06.yaml 4`, one try per shard, no failures).
Assembled with music preset A, `intro: title_song` and `outro: ending_song` (v6 sting). Aswatthaman is A_1
(`voices/aswatthaman/ref.wav`). Speech tags stay with Sauti. No crowd voice: the joint sentence is Sauti.

**Master:** `episodes/ep06.wav` (not committed) 1171.73 s = **19:32**, −16.1 LUFS (bs1770), sample peak −2.0 dBFS.
MP3 `samples/ep06_v1.mp3` (192k mono): **−16.0 LUFS, −1.5 dBTP**, 27 MB.
No missing lines. Speech-to-music minimum 14.0 dB (preset floor 14), average 17.1 dB.

**Intro / outro:** v6 sting title 0:00–0:45.2, first line at 0:42.7 (2.5 s crossfade). Last line
("The number of slokas is seven hundred and seventy-five") ends at 19:12, then the music tail and the ending sting.

**Voices:** Sauti 111, Krishna 2, Aswatthaman 2. Krishna's offer at 2:44, the vow (A_1) at 14:05, the weapon at 16:04,
"This shall not be" at 16:09.

**Per-line QA** (`tools/qa_episode.py`, Whisper, speaker identity, tails): 80 OK, 35 flagged; none needs a retake.
- WER flags on the sloka-count lines (0009, 0036, 0047, 0066, 0115) and "sixty-seven" / "one hundred and seventy"
  (0008, 0056) are digits: ASR writes "2050", "6,698", "775".
- "ending not heard" on those same count lines is the digit transcript, not a cut-off. The vow (0080) is complete
  ("I will not take off armor"). 0014's abrupt-end flag still has "which of you?"
- Krishna heard as Kṛṣṇa (0013, 0027, 0041, 0093, 0109) and Akshauhini as "Akshawini" (0014). 0093 is three words;
  WER 1.0 is "Then"/"than" plus the Devanagari spelling.
- Duration flags on short lines (0069, 0079, 0094, 0095, 0107) are a pause on a short sentence. The words are all there.
  0095 ("Neutralised Aswatthaman's speech") is slow (2.9 s) and intact.
- Voice-closest flags (0058 santanu, 0107 and 0111 vyasa, 0113 vaisampayana) sit next to Sauti's own similarity
  0.73–0.88. No clip flags, no internal silence over 1.2 s.
- Names the meter missed are ASR spellings: Amba "Amber", Dhrishtadyumna "Brishtadyumna", Aswatthaman "Daswathaman"
  in the death list (0062), Stri "Stree" (0103). Jambu is not in a flagged line.

**Worth a human listen:** Akshauhini on Krishna's offer (2:44), Aswatthaman in the death list (0062), and the
still-unverified harness names Akshauhini, Stri, and Jambu.
