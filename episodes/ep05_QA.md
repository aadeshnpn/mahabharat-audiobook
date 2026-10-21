# Episode 5 v1: render QA (2026-10-20)

**Render:** 52 lines in 5 shards (~4 min each; `tools/render_sharded.sh`, one try per shard, no failures), 19:30–20:10 MDT.
Assembled with music preset A, `intro: title_song` and `outro: ending_song` (v6 sting).

**Master:** `episodes/ep05.wav` (not committed) 1080.34 s = **18:00**, -16.1 LUFS (bs1770), sample peak -2.0 dBFS.
Shorter than the 19:40 estimate: Sauti read the catalogue at ~150 wpm vs the 138 wpm model (narration ~16:59).
MP3 `ep05_v1.mp3` (192k mono): 1080.38 s, **-16.0 LUFS, -1.7 dBTP** (ffmpeg ebur128), 25.9 MB.
Chat copy `ep05_v1_chat.mp3` (160k): -16.0 LUFS, -1.6 dBTP, 21.6 MB.
Music: min speech-to-music 15.9 dB (preset floor 14). No missing lines.

**Intro / outro:** v6 sting title 0:00–0:45.2, first line at 0:42.71 (2.5 s crossfade); ASR hears "The high-souled
Vyasa composed these hundred parvas…" right at the join. The last line ("The number of slokas is eleven thousand, six
hundred and sixty-four", 17:36) is intact, then the music tail, then the ending sting at 17:42.5; ASR hears the 2.63b
verse ending in प्रणश्यति.

**Shard joins** (ASR across ±7 s): 0010/0011 at 4:12.6, 0022/0023 at 7:46.5, 0032/0033 at 11:16.1, 0043/0044 at
14:47.8 all read straight through with nothing dropped or doubled.

**Per-line QA** (`tools/qa_episode.py`, Whisper WER, speaker identity, tails): 31 OK, 21 flagged; on review none needs a retake.
- WER flags on 0020, 0021, 0028, 0051, 0052 are numbers (ASR writes "227", "8,884", "11,664").
- 0003 (wer 0.59, "ending not heard"): the QA ASR stopped early; a re-transcription hears the whole line
  ("…and the Pauloma, of the sons of Bhrigu"). 0005 and 0014 "cut-off" flags: the transcripts end on the last word.
- "repetition/insertions" flags (0002, 0007, 0014, 0023, 0033, 0036, 0043, 0047) are long list lines with repeated
  "the … of"; the transcripts match the text (WER 0.01–0.18).
- Voice-closest flags (0044 → vyasa 0.77, 0049 → devas_chorus) are within the meter's noise; own-voice 0.77–0.92.
- Names missed are ASR spellings: Kama→Karna (spoken Karna, as fixed), Pauloma "Paloma", Arshtishena "Ashdishaynu".

**Hard names as heard:** Uchchaihsrava "Uchayzrava", Rishyasringa "Rishasringa", Sukanya, Chyavana "Kyavana",
Saryati, Tarkshya "Tarksha", Animandavya "Anamandavya", Hiranyapura, Pulastya, Vrihidraunika "Vrihedraunika".
Worth a human listen: Chyavana (13:21), Uchchaihsrava (1:20), and the pending names from the harness pass
(Aurva, Vena, Raivya, Kirmira, Gaya, Sauva).
