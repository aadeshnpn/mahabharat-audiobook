"""`mbh song check|takes|score|render|verify` (see docs/SONGS.md). Heavy imports happen inside each command."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def add_song_commands(sub) -> None:
    song = sub.add_parser("song", help="sung pieces: title songs, shlokas")
    acts = song.add_subparsers(dest="action", required=True)

    check = acts.add_parser("check", help="parse the song config, validate the melody against the raga, print timing")
    check.add_argument("spec", type=Path)
    check.set_defaults(func=cmd_check)

    takes = acts.add_parser("takes", help="speak each line with the singer voice (VoxCPM2; render venv)")
    takes.add_argument("spec", type=Path)
    takes.add_argument("--lines", help="comma-separated line ids")
    takes.add_argument("--voice", help="voice id override (voices/<id>/ref.wav)")
    takes.add_argument("--voice-ref", help="reference wav override (repo-relative)")
    takes.add_argument("--seeds", help="comma-separated seeds")
    takes.set_defaults(func=cmd_takes)

    score = acts.add_parser("score", help="ASR-score takes against the Devanagari text (pocket venv)")
    score.add_argument("spec", type=Path)
    score.set_defaults(func=cmd_score)

    render = acts.add_parser("render", help="sing the takes onto the melody, arrange and master (render venv)")
    render.add_argument("spec", type=Path)
    render.add_argument("--out", type=Path, required=True)
    render.add_argument("--lines", help="comma-separated line ids (default: the structure)")
    render.add_argument("--voice", help="voice id override")
    render.add_argument("--octave", type=float, help="sing this many octaves above sa_hz")
    render.add_argument("--take", action="append", default=[], help="LINE=TAKE_FILE (repeatable)")
    render.set_defaults(func=cmd_render)

    asr = acts.add_parser("asr", help="ASR-score any audio file against line text(s) (pocket venv)")
    asr.add_argument("spec", type=Path)
    asr.add_argument("files", nargs="+", type=Path)
    asr.add_argument("--lines", required=True, help="comma-separated line ids the audio should contain")
    asr.set_defaults(func=cmd_asr)

    ace = acts.add_parser("ace", help="ACE-Step 1.5 sung + arranged rendition (text2music or cover; ace venv)")
    ace.add_argument("spec", type=Path)
    ace.add_argument("--out", type=Path, required=True)
    ace.add_argument("--lines", help="comma-separated line ids (default: all)")
    ace.add_argument("--seed", type=int, default=0)
    ace.add_argument("--mode", choices=["text2music", "cover"], default="text2music")
    ace.add_argument("--src", type=Path, help="cover mode: our WORLD-sung render to re-sing")
    ace.add_argument("--cover-strength", type=float)
    ace.add_argument("--duration", type=float)
    ace.set_defaults(func=cmd_ace)

    mst = acts.add_parser("master", help="master a file to the song's LUFS / true-peak target, with trim and fades")
    mst.add_argument("spec", type=Path)
    mst.add_argument("src", type=Path)
    mst.add_argument("out", type=Path)
    mst.add_argument("--start", type=float, default=0.0)
    mst.add_argument("--end", type=float)
    mst.add_argument("--fade-in", type=float, default=1.0)
    mst.add_argument("--fade-out", type=float, default=3.0)
    mst.set_defaults(func=cmd_master)

    verify = acts.add_parser("verify", help="ASR-score a rendered song (mix and dry vocal; pocket venv)")
    verify.add_argument("spec", type=Path)
    verify.add_argument("report", type=Path, help="the .json written next to the rendered wav")
    verify.set_defaults(func=cmd_verify)


def _spec(path):
    from mbh.song.spec import load_song
    return load_song(path)


def cmd_check(args: argparse.Namespace) -> int:
    from mbh.song.melody import swara_hz
    spec = _spec(args.spec)
    print(f"{spec.id}: raga {spec.raga}, Sa {spec.sa_hz} Hz, {spec.tempo_bpm} bpm ({spec.beat_s:.3f} s/beat)")
    for line in spec.lines:
        beats = max(n.start_beat + n.beats for n in line.notes)
        sung = [n for n in line.notes if not n.is_rest]
        lo = min(swara_hz(n.swara, spec.sa_hz) for n in sung); hi = max(swara_hz(n.swara, spec.sa_hz) for n in sung)
        print(f"  {line.id}: {len(line.syllables)} syllables, {beats:g} beats = {beats * spec.beat_s:.1f} s, range {lo:.0f}-{hi:.0f} Hz")
    return 0


def _voice(args) -> dict:
    v = {}
    if getattr(args, "voice", None):
        v["id"] = args.voice
    if getattr(args, "voice_ref", None):
        v["ref"] = args.voice_ref
    if getattr(args, "octave", None) is not None:
        v["octave"] = args.octave
    return v


def cmd_takes(args: argparse.Namespace) -> int:
    from mbh.song.render import make_takes
    spec = _spec(args.spec)
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else None
    make_takes(spec, args.lines.split(",") if args.lines else None, _voice(args), seeds)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    from mbh.song.asr import score_takes
    score_takes(_spec(args.spec))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from mbh.song.render import render
    spec = _spec(args.spec)
    takes = dict(t.split("=", 1) for t in args.take)
    report = render(spec, args.out, line_ids=args.lines.split(",") if args.lines else None, voice=_voice(args), takes=takes)
    print(json.dumps({k: report[k] for k in ("out", "seconds", "voice")} | {"lines": [(r["line"], r["take"]) for r in report["lines"]],
                     "lufs": report["master"].get("after")}, ensure_ascii=False))
    return 0


def cmd_asr(args: argparse.Namespace) -> int:
    from mbh.song.asr import score_file
    spec = _spec(args.spec)
    ref = " ".join(spec.line(i).text for i in args.lines.split(","))
    for f in args.files:
        r = score_file(f, ref)
        print(f"{r['score']:.2f} {f.name} {r['asr']}", flush=True)
    return 0


def cmd_ace(args: argparse.Namespace) -> int:
    from mbh.song.ace import generate
    spec = _spec(args.spec)
    info = generate(spec, args.out, line_ids=args.lines.split(",") if args.lines else None, seed=args.seed,
                    mode=args.mode, src=args.src, duration=args.duration, cover_strength=args.cover_strength)
    print(json.dumps({k: info[k] for k in ("out", "mode", "seed", "seconds", "gen_s")}))
    return 0


def cmd_master(args: argparse.Namespace) -> int:
    from mbh.song.master import master_file
    spec = _spec(args.spec)
    print(json.dumps(master_file(args.src, args.out, float(spec.master.get("lufs", -16)), float(spec.master.get("true_peak_db", -2)),
                                 args.start, args.end, args.fade_in, args.fade_out)))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from mbh.song.asr import score_render
    for row in score_render(_spec(args.spec), args.report):
        print(f"{row['stem']:10s} {row['line']:6s} {row['score']:.2f} {row['asr']}")
    return 0
