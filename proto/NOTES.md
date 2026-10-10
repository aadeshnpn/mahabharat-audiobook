# Prototype notes: CPU bake-off (Oct 9, 2026, ~21:45–22:25 MT)

**Box:** 8 vCPU Intel Xeon (AVX-512, AMX-BF16), 15 GB RAM, no GPU. Python 3.12 venvs with CPU-only torch 2.14.1.
**Nothing was pushed to GitHub.**

## What ran

| Step | Engine | Result | Timing on this box |
|---|---|---|---|
| Voice design, 8 characters × 2 candidates (`out/design/*_vox_*`) | VoxCPM2 (2B, bf16, 10 diffusion steps) | ✅ all 16 clips intelligible (ASR WER ≤4.3% on 13 of 16; the other three were 8.7%, 13%, and 18% (Kunti ×2, one Satyavati candidate)) | load 15 s; **RTF 2.5–3.2** (≈25–40 s per ~10 s clip) |
| Voice design, 3 characters (`*_qwen_0`) | Qwen3-TTS-1.7B-VoiceDesign (bf16, official PyTorch, no flash-attn) | ✅ works, WER 0–7% | load 33 s; **RTF 2.9–3.1** |
| End-to-end excerpt, 1:100 Bhishma's vow, 13 segments, 6 voices | VoxCPM2 controllable cloning, 10 steps | ✅ **mean WER 4.7%, speaker identity 13/13** (each clip's closest reference embedding was its own character); own-ref cosine 0.79–0.94 | 298 s compute for 99 s of audio → **RTF 3.02** |
| Same excerpt | VoxCPM2, 5 steps | ✅ mean WER 4.0%, identity 13/13, own-ref cosine slightly lower (0.75–0.93) | **RTF 2.22** |
| Same excerpt, cloning designed refs | Pocket TTS | ❌ **blocked**: the cloning weights are gated on Hugging Face (you have to accept the terms at https://huggingface.co/kyutai/pocket-tts and log in with an HF token) | – |
| Same excerpt, built-in catalog voices (speed test only; not Indian-accented, not our cast) | Pocket TTS (100M) | ✅ WER 5.1% | **RTF 0.39** (about 2.5× faster than real time), load <1 s |

## Projections for all of Book 1 (≈229k words ≈ 25–26 h of audio; my arithmetic)
- VoxCPM2 at 10 steps on this box: ≈ **77 CPU-hours (~3.2 days)**. At 5 steps: ≈ **57 h (~2.4 days)**.
- Pocket TTS: ≈ **10 h**, if the gated cloning weights are unlocked.
- Voice design is negligible: about 30 s per candidate, so 50 characters × 6 candidates ≈ 2.5 h.

## Problems hit and fixes
1. **VoxCPM2 was OOM-killed (exit 137)** on 15 GB. It builds the model in fp32 (~9 GB) before casting to bf16. Fix: `torch.set_default_dtype(torch.bfloat16)` before `from_pretrained(..., optimize=False)`. Peak RSS was then about 6–7 GB. (`optimize=True` uses torch.compile, which only targets CUDA.)
2. faster-whisper with the installed PyAV rejected file paths (`metadata_errors` kwarg). Fix: pass a numpy array loaded via librosa.
3. resemblyzer needs `setuptools<70` (for `pkg_resources`).
4. Pocket TTS cloning is gated (see above). Unblocking it needs Aadesh's HF account.

## Observations
- **Instructions work at the identity level:** the VoxCPM2 cast stayed clearly separated. Cross-character cosine was 0.43–0.76, against 0.8–0.94 for the same character.
- Short lines ("She answered,", "I bestow my daughter!") have worse RTF (about 4) and a weaker identity match. The VoxCPM docs also say inputs under ~1 s sound weak. Later we should merge tiny narration tags into neighbouring segments or pad them with context.
- Name errors in the ASR transcripts (Bishma/Pishma, "Sati"/"Salty" for Sauti) are partly ASR mistakes and partly TTS pronunciation. **A Sanskrit pronunciation lexicon is required** (VoxCPM2 accepts CMUdict phonemes).
- KMG quote nesting is irregular (unclosed `'` quotes), so automatic attribution needs an LLM pass. The excerpt script (`excerpt_100.json`) was hand-attributed as the template for the Phase 5 format. I made two small normalizations: dropped the "(study and meditation in celibacy)" gloss, and changed "Bhishma (the terrible)" to "Bhishma, the terrible!".
- **Accent:** every prompt asked for a "clear Indian English accent". I can't judge accent objectively from the box. **Listening is required.** If it isn't convincing, try Indic Parler-TTS or OmniVoice (`indian accent`) as the reference-clip generator (not tried yet).
- Celestial voice: a single designed voice plus an ffmpeg multi-tap echo (`aecho`) in assembly. Crude but workable. A proper chorus (2–3 voices layered) would be better.

## Files
- Samples to listen to (`/workspace/mahabharat/samples/`):
  - `excerpt_1-100_bhishma_vow_voxcpm2.mp3`: **main demo**, full cast, 10 steps, about 100 s, −16 LUFS
  - `excerpt_1-100_bhishma_vow_voxcpm2_5steps.mp3`: the same at 5 steps (faster), for an A/B comparison
  - `excerpt_1-100_bhishma_vow_pocket_catalog_voices.mp3`: Pocket TTS speed/quality reference (stock voices)
  - `voices/*.mp3`: the selected designed reference voices (Sauti, Vaisampayana, Bhishma, Kunti, Santanu, Satyavati, Dasa, devas chorus) plus the Qwen3 VoiceDesign versions of Vaisampayana, Bhishma, and Satyavati
- All candidates: `proto/out/design/` (2 per character). Per-segment renders: `proto/out/excerpt_*`.
- Scripts: `design_vox.py`, `design_qwen.py`, `render_vox.py`, `render_pocket.py`, `qa.py` (ASR WER + F0 + speaker similarity), `qa_render.py`, `assemble.py` (gaps, FX, loudnorm, MP3).
- Logs/metrics: `proto/logs/*.json|log`, `out/*/render_log.json`, `out/*/qa.json`.

## Open questions for Aadesh
1. **Listen:** do the voices sound acceptably Indian-English and "ancient" yet clear? Which design engine do you prefer, VoxCPM2 or Qwen3?
2. **Speech tags:** keep "Bhishma said," in the narrator's voice (faithful to KMG), or drop them for a radio-drama feel?
3. **Parenthetical glosses** like "Brahmacharya (study and meditation in celibacy)": read them, drop them, or voice them as a narrator aside?
4. **Frame narrators:** a distinct voice each for Sauti (outer frame) and Vaisampayana (inner frame)? And should the Rishis/Saunaka/Janamejaya interjections be voiced?
5. **Aging characters** (e.g. Bhishma young → old within Book 1): one voice, or versioned voices per era?
6. **Compute:** OK with about 2.5–3 days of CPU on this box for Book 1 with VoxCPM2? Or run on your own machine? (Its specs would change the estimate.)
7. **Pocket TTS:** willing to accept Kyutai's HF terms and provide an HF token, so the fast CPU cloning path can be tested?
8. **Licensing/distribution:** personal use, or public release? A public release rules out IndexTTS2 and Fish S2 unless authorized; the current stack is all Apache/MIT.
9. **LLM for extraction/attribution:** is a local open model required (CPU-only makes that slow), or is a hosted LLM acceptable for the text-analysis phases?
