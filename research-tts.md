# Mahabharata Audiobook: Open-Source TTS Research (CPU-only)

*Researched Oct 9, 2026 (MT). Constraint: **CPU-only inference, no GPU; slow is acceptable.** Star counts and last-push dates come from the GitHub API on Oct 9, 2026. Every speed number below is quoted from the cited source. Where nobody has published a CPU number, the table says so.*

**RTF (real-time factor)** = seconds of compute per second of audio. Below 1 is faster than real time. Above 1 is slower.

---

## 1. Source text: Book 1 (Adi Parva) structure

- Site: https://mahabharata-online.github.io/ (repo `mahabharata-online/mahabharata-online.github.io`, branch `main`). The text is KMG, from the Sacred-Texts/Gutenberg digitization. The site maintainer notes that Books 1–4 were proofed at Distributed Proofreaders.
- URL scheme: `/<book>/<section>.html`. Book 1 runs from `/1/1.html` to `/1/236.html`, which is **236 sections**. That count matches `sections_per_parva = {1: 236, ...}` in `/resources/js/build-parva-sidebar.js`. The Sanskrit original is at `/sanskrit/1/<n>.html`.
- Body text sits in `<div class="mbh-content" id="to_index">`. Clean static HTML, easy to scrape. I fetched all 236 pages as a check.
- **Size:** about **230,000 words** (my HTML-stripped count: 230,164). Shortest section is 151 words, longest 8,641 (section 1), median 793.
- **Sub-parvas.** Each section opens with a header such as "(Sambhava Parva continued)". These are the natural chapter groupings:

| Sub-parva | Starts at section |
|---|---|
| Anukramanika (1) / Parva-sangraha (2) | 1 |
| Paushya | 3 |
| Pauloma | 4 |
| Astika | 13 |
| Adivansavatarana | 59 |
| Sambhava (largest, 65–142) | 65 |
| Jatugriha | 143 |
| Hidimva-vadha | 154 |
| Vaka-vadha | 159 |
| Chaitraratha | 167 |
| Swayamvara | 186 |
| Vaivahika | 195 |
| Viduragamana | 202 |
| Rajya-labha | 210 |
| Arjuna-vanavasa | 215 |
| Subhadra-harana | 221 |
| Haranaharana | 223 |
| Khandava-daha | 224–236 |

- **Dialogue format matters for casting.** The text is a frame narrative: Sauti tells Saunaka and the Rishis what Vaisampayana told Janamejaya, and Vaisampayana's account contains the characters' speech. Speech is introduced as `"X said, '...'"` with nested quotes. Counts of "`<Name> said,`" in Book 1: Vaisampayana 142, Sauti 59, Janamejaya 24, Saunaka 15, Ashtaka 10, Arjuna 9, Vasishtha 9, Yayati 8, Yudhishthira 7, Kunti 6, and so on. The speaker tags are explicit, so attribution can be largely rule-based plus an LLM pass. The nesting depth of quotes tells you which narrator layer you are in.
- **Audio length estimate (my arithmetic, not sourced):** 230k words at about 150 wpm is roughly 25–26 hours of audio for Book 1.

---

## 2. Candidates verified (status as of Oct 2026)

### 2a. Voice design: create a voice from a text description

| Model / repo | Stars, last push, license | Design input | Size | CPU support and documented CPU speed | Indian-English accent | Notes |
|---|---|---|---|---|---|---|
| **VoxCPM2** – [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) | 38.5k, 2026-10-08, Apache-2.0 (code and weights) | Free-form description in parentheses: `"(A deep, elderly male voice, slow and grave)text"` ([usage guide](https://voxcpm.readthedocs.io/en/latest/usage_guide.html)) | 2B, 48 kHz, 30 languages including English and Hindi | **Python on CPU works.** Zen 5 / Strix Halo CPU: RTF **1.06–1.25** at 5 diffusion steps and **1.58–1.93** at 10 steps ([sleepingrobots benchmark](https://sleepingrobots.com/dreams/voxcpm-strix-halo/)). The blog notes a one-line attention-mask fix was needed on PyTorch 2.11 CPU. GGUF via [VoxCPM.cpp](https://github.com/bluryar/VoxCPM.cpp): VoxCPM2 Q4_K at RTF 1.55 (16 threads), but v2 support is labeled "preliminary". | Not explicitly listed. You have to prompt for it ("Indian English accent") and test. | The same model also does **controllable cloning** (see 2b). That gives one model for both design and rendering. Tech report: ICLR 2026 (VoxCPM v1). |
| **Qwen3-TTS-12Hz-1.7B-VoiceDesign** – [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | 13.7k, 2026-03-17, Apache-2.0 | `generate_voice_design(text, language, instruct="...")`, a rich natural-language instruct covering timbre, age, emotion, and style ([docs](https://qwenlm-qwen3-tts.mintlify.app/concepts/models)) | 1.7B; 10 languages (no Hindi) | Official PyTorch on CPU is slow: 0.6B RTF **4.5–5.8** on a Ryzen 9 7950X ([gabriele-mastrapasqua/qwen3-tts table](https://github.com/gabriele-mastrapasqua/qwen3-tts)). The C engine (MIT) runs 1.7B at RTF about 2–4.4 on an M1, and 0.6B at about 1.3. GGUF/llama.cpp: 1.7B RTF 1.3 on CPU ([HaujetZhao/Qwen3-TTS-GGUF](https://github.com/HaujetZhao/Qwen3-TTS-GGUF)), Q4 RTF 1.14 on an i9-13980HX ([Rust port](https://github.com/QwenLM/Qwen3-TTS/discussions/187)). **Check before relying on it:** the third-party ports are confirmed for Base/CustomVoice/clone, but I did not confirm they support the VoiceDesign checkpoint. Official PyTorch CPU is fine for one-off design work. | Not listed; 10 languages. Has to be prompted and tested. | Documented "voice design, then clone" workflow. Paper: [arXiv:2601.15621](https://arxiv.org/abs/2601.15621). |
| **OmniVoice** – [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice) | 14.4k, 2026-10-06, Apache-2.0 | **Categorical** attributes only: gender, age, pitch, whisper, accent ([voice-design.md](https://github.com/k2-fsa/OmniVoice/blob/master/docs/voice-design.md)) | 600+ languages | Strix Halo CPU: design RTF **0.56**, clone RTF 1.52 ([sleepingrobots](https://sleepingrobots.com/dreams/voxcpm-strix-halo/)) | **Yes: an explicit `indian accent` attribute** for English text | 16 kHz output. Too coarse for character psychology, but useful as an accent anchor. |
| **Indic Parler-TTS** – [ai4bharat/indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) (on [huggingface/parler-tts](https://github.com/huggingface/parler-tts)) | Parler repo 5.6k, last push **2024-12** (stale); model Apache-2.0 | Free-form description of gender, pitch, pace, expressivity, recording quality, plus named speakers | Parler Mini (~0.9B per the Parler family; not re-verified) | Runs in PyTorch on CPU. **No published CPU RTF.** | **Yes: "officially supports Indian English accents"**, with 21 English speakers (Thoma, Mary, ...) and Sanskrit and Hindi supported | Older-generation quality. Good fallback for accent-true reference clips. |
| Parler-TTS Mini/Large v1 | same repo, Apache-2.0 | Free-form description | 880M / 2.2B | CPU possible; no RTF published | No (accent is "planned" in the TODO list) | Superseded by the models above. |
| Fish Audio S2 Pro – [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) | 33k, 2026-10-05, **Fish Audio Research License** (non-commercial) | Free-form inline tags `[whisper in small voice]`, 15k+ tags; it is mostly a style controller, not a speaker designer | 4B | None documented; impractical on CPU | – | Strong quality ([arXiv:2603.08823](https://arxiv.org/abs/2603.08823)), but too large for CPU and the license is restrictive. |

### 2b. Rendering: zero-shot cloning from a reference clip, with emotion control

| Model / repo | Stars, last push, license | Emotion / style control | Size | CPU support and documented CPU speed | Long-form | Notes |
|---|---|---|---|---|---|---|
| **VoxCPM2 controllable cloning** | (above) Apache-2.0 | `reference_wav_path=` sets the timbre. A parenthesized instruction sets emotion, pace, and style: `"(grief-stricken, trembling, slow)text"`. Hi-Fi mode (reference plus transcript) gives the best similarity but **ignores the instruction**. ([usage guide](https://voxcpm.readthedocs.io/en/latest/usage_guide.html)) | 2B | Same numbers as above: RTF about 1.1–1.9 on a high-end CPU. VoxCPM.cpp on an i5-12600K (8 threads) for **v1.5**: RTF 4.29 ([issue #194](https://github.com/OpenBMB/VoxCPM/issues/194)). Expect noticeably slower on mid-range CPUs. | The docs say long text causes speed-up, buzzing, or no stopping. Generate per sentence or paragraph and concatenate. Lower `cfg_value` toward 1.5–1.6 for stability. LoRA fine-tuning is offered for "production-grade consistency". | Supports CMUDict phoneme input `{HH AH0 L OW1}`, which helps with Sanskrit names. |
| **Pocket TTS** – [kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts) | 9.9k, 2026-10-07, MIT | No explicit emotion parameter. Cloning captures "emotion, accent, cadence" from the reference clip ([tech report](https://kyutai.org/pocket-tts-technical-report/)), so emotion is chosen by picking a reference clip | **100M** | **CPU-first.** "~6x real-time on a MacBook Air M4 CPU, uses only 2 cores", optional int8 `--quantize`, voice embeddings exported to `.safetensors` | "Can handle infinitely long text inputs" | English plus 5 European languages. Tech report: WER 1.84, better than F5-TTS and Chatterbox Turbo in their table. |
| **Chatterbox** (original 500M / Turbo 350M / Nano 110M) – [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) | 26.8k, 2026-07-21, MIT | Original: `exaggeration` knob (0.5 by default, 0.7+ for drama) plus `cfg_weight`. Turbo/Nano: paralinguistic tags `[laugh]` etc. | 110M–500M | Nano: "3x faster than realtime on 8 CPU cores". No CPU numbers for the 500M original. | Not documented | Output carries the **PerTh watermark**. Resemble has stopped offering these as commercial products; the models stay open. |
| IndexTTS-2 / 2.5 – [index-tts/index-tts](https://github.com/index-tts/index-tts) | 24.4k, 2026-09-29, **bilibili Model Use License** (commercial use needs written authorization) | Best emotion control available: emotion reference audio, an 8-dimensional vector `[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]`, `emo_text`, `emo_alpha`, plus duration control ([paper arXiv:2506.21619](https://arxiv.org/abs/2506.21619)) | ~1.5B+ | `device="cpu"` works in FP32. No official CPU RTF. The community MNN port of 2.5 measures RTF **3.16–3.25** on an M5 Pro with 4 threads ([pypi index-tts-2.5-mnn](https://pypi.org/project/index-tts-2.5-mnn/)) | Not documented | Its index-tts2.com page claims Apache-2.0, but the official repo says the bilibili license. Trust the repo. |
| Qwen3-TTS Base (cloning) | (above) | No instruct on Base. CustomVoice/VoiceDesign take instructs but use their own speakers | 0.6B / 1.7B | Best CPU tooling: C engine 0.6B RTF about 1.3 on an M1, int8/int4. A 4-vCPU cloud box measured RTF 2.5–3.2 ([ocdevel](https://ocdevel.com/blog/20260711-quantized-cpu-tts)) | Streaming | Cloning works without emotion steering, so emotion has to come from the reference, as with Pocket. |
| F5-TTS – [SWivid/F5-TTS](https://github.com/SWivid/F5-TTS) | 15.4k, 2026-09-21, MIT code (the original weights are CC-BY-NC) | Emotion comes from the reference clip | 336M | Not faster than real time on CPU (Pocket TTS report) | Chunked | Mature, but nothing it offers beats the options above. |
| NeuTTS Air – [neuphonic/neutts](https://github.com/neuphonic/neutts-air) | 6.3k, 2026-07-30, custom license (NOASSERTION) | Reference clip only | ~0.5B; Q4/Q8 GGUF | Designed for CPU (llama.cpp backbone) | – | English cloning on CPU; little else. |
| Kokoro-82M – [hexgrad/kokoro](https://github.com/hexgrad/kokoro), [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 9.2k, push 2025-08, Apache-2.0 | None; fixed voice packs | 82M | Very fast on CPU, ONNX | – | **No cloning and no design.** Possible as a fast draft narrator only. |
| VibeVoice – [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | 54.7k, MIT | Little explicit control | 1.5B / 7B | CPU "slow, not real-time"; vibevoice.cpp exists | 90 minutes, 4 speakers in a single pass ([arXiv:2508.19205](https://arxiv.org/abs/2508.19205)) | Microsoft disabled the TTS repo/playground after misuse; weights remain on HF. Four speakers is far too few for a full cast. |
| Higgs Audio v2 ([boson-ai](https://github.com/boson-ai/higgs-audio), 8.4k), Dia ([nari-labs](https://github.com/nari-labs/dia), 19.4k, push 2025-11), Orpheus (6.3k, push 2025-12), Sesame CSM (14.7k, push 2025-05), Zonos (7.2k, push 2025-03), Spark-TTS (11k, push 2025-04), StyleTTS2 (6.4k, push 2024-08), Coqui XTTS ([idiap fork](https://github.com/idiap/coqui-ai-TTS) maintained, CPML weights), CosyVoice ([now QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice), 23.9k), ChatTTS (AGPL), KittenTTS (tiny, no cloning), MaskGCT/Amphion (MIT) | | | | Either stale (no pushes in 2026), GPU-oriented with no CPU story, or beaten on CPU by the picks above | | Not recommended for this project. |

---

## 3. Recommended CPU-only stack

### Voice design (offline, one-time per character, so slowness doesn't matter much)
- **Top pick: VoxCPM2 voice design.** Apache-2.0, free-form descriptions, Python works on CPU (RTF about 1–2 on a high-end CPU), 48 kHz, and Hindi among its languages. It is **the same model as the renderer**, so a designed clip clones back into the same latent space with less mismatch.
- **Alternative: Qwen3-TTS-1.7B-VoiceDesign.** Probably the strongest at following rich instructions, and it has a documented design-then-clone flow. It is slow on CPU through official PyTorch, which is acceptable for designing roughly 50–100 characters × ~15 s clips.
- **Accent anchors, if neither nails Indian English:** **Indic Parler-TTS** (officially supports Indian English, Apache-2.0) or **OmniVoice** (`indian accent` attribute, fast on CPU). You can also run a two-step chain: generate an Indian-accent clip with one of these, then use it as the reference so VoxCPM2 carries the accent while its instruction adjusts age and timbre. A bake-off will decide.

### Rendering (bulk: ~25 h of audio for Book 1)
- **Top pick: VoxCPM2 controllable cloning.** `reference_wav_path=<character>.wav` plus `"(emotion/pace instruction)line"`. Per-line emotion control on CPU under Apache-2.0. Rough compute (my arithmetic): RTF 1.25–1.9 × 25.6 h gives about **32–49 CPU-hours** on a high-end CPU like the benchmarked Zen 5. A mid-range desktop could take 2–3× longer. It runs unattended and can be sharded by section.
- **Alternative: Pocket TTS.** 100M parameters, CPU-first, about 6× real time on an M4 (Book 1 in roughly 4–5 h by my arithmetic), and it handles long text natively. Emotion is set by building a small **emotion bank per character** (neutral, angry, grieving, and so on), designed as reference clips and picked per line. Pick this if VoxCPM2 is too slow on your CPU or drifts on long text.
- Honorable mention: **IndexTTS-2.5.** Best emotion control (8-dimensional vector), but the license is restrictive and the community MNN port runs at RTF about 3.2. Only consider it if the audiobook stays strictly non-commercial.

### How the pieces combine
```
characters.yaml (LLM-extracted: name, age, gender, role, temperament, backstory)
   │  LLM writes a voice prompt, e.g. "Elderly Indian man, deep resonant baritone,
   │  slow measured cadence, grave and compassionate, clear Indian-English diction"
   ▼
[Design]  VoxCPM2 (or Qwen3-VoiceDesign / Indic Parler) → N candidates per character
   │  pick the best by ear plus a speaker-embedding distance check against the other cast
   ▼
voices/<character>/ref_neutral.wav (10–20 s, clean) [+ ref_angry.wav, ref_sad.wav for Pocket]
   │  freeze the reference; optional VoxCPM2 LoRA later for the busiest characters (Sauti, Vaisampayana)
   ▼
[Script] per section: segments = [{speaker, text, emotion, pace}] from the "X said, '...'" parsing plus an LLM
   │  pronunciation lexicon for Sanskrit names (VoxCPM2 accepts CMUDict phonemes)
   ▼
[Render] VoxCPM2: generate(text="(emotion, pace)line", reference_wav_path=ref) per sentence
   │  (or Pocket TTS with the emotion-matched reference embedding)
   ▼
[Post] loudness normalization, room/reverb per narrative layer, pauses, optional ambience/music → section MP3/M4B with chapters
```

### Key risks to test first (Phase 0 bake-off, about a day of CPU time)
1. **Indian-English accent fidelity.** No major design model guarantees it except Indic Parler-TTS and OmniVoice. Run 5 characters through VoxCPM2, Qwen3, and Indic Parler, with and without accent wording.
2. **Identity stability under emotion.** Does VoxCPM2's instruction for anger or grief shift the timbre? Measure speaker-embedding similarity against the reference.
3. **Sanskrit names** (Vaisampayana, Janamejaya, Dhritarashtra). Test raw text against phoneme overrides.
4. **Actual RTF on Aadesh's CPU** for VoxCPM2 (5 vs 10 steps), Pocket TTS, and Qwen3 0.6B in the C engine.
5. **Long-form drift.** Render one full section (about 800 words) per engine and listen for speed-up, buzzing, or truncation.

## 3b. Measured on the Grok Bot box (8 vCPU Xeon, AVX-512/AMX, 15 GB RAM, no GPU)
See `proto/NOTES.md` for details.
- VoxCPM2 voice design: RTF 2.5–3.2 (10 steps). Controllable cloning of a 13-segment, 6-voice excerpt: **RTF 3.02 at 10 steps, 2.22 at 5 steps**. Mean ASR WER about 4–5%; speaker identity 13/13. Needed a bf16 default-dtype fix to avoid OOM at 15 GB.
- Qwen3-TTS 1.7B VoiceDesign (official PyTorch, CPU): RTF 2.9–3.1.
- Pocket TTS (catalog voices): **RTF 0.39**. Its voice-cloning weights are **gated** on Hugging Face (they need an account plus accepted terms), so cloning our designed voices was not tested.
- Projection for Book 1 on this box: about 57–77 CPU-hours with VoxCPM2, or about 10 h with Pocket TTS.

## 4. Relevant papers
- Lyth & King, *Natural language guidance of high-fidelity TTS with synthetic annotations* (2024): the basis of Parler-TTS. arXiv:2402.01912
- Qwen3-TTS Technical Report: arXiv:2601.15621
- IndexTTS2 (emotion/timbre/duration disentanglement): arXiv:2506.21619
- VibeVoice Technical Report (long-form multi-speaker): arXiv:2508.19205
- Fish Audio S2 technical report: arXiv:2603.08823
- VoxCPM tokenizer-free TTS (ICLR 2026) and the VoxCPM2 technical report: linked from https://github.com/OpenBMB/VoxCPM
- Kyutai Pocket TTS tech report: https://kyutai.org/pocket-tts-technical-report/
- F5-TTS (flow matching): arXiv:2410.06885
