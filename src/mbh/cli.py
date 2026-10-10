"""Command line: mbh episode build|estimate|breaks|render|assemble|export-script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mbh.episode.assemble import assemble
from mbh.episode.breaks import suggest_for_spec, suggest_in_section
from mbh.episode.build import build_episode
from mbh.episode.markdown import render_markdown
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.render import RenderResult, VoxCPM2Backend, render_script
from mbh.episode.spec import load_spec
from mbh.episode.timing import format_duration, load_timing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mbh")
    sub = parser.add_subparsers(dest="command", required=True)
    episode = sub.add_parser("episode", help="build and review episode scripts")
    actions = episode.add_subparsers(dest="action", required=True)

    build = actions.add_parser("build", help="write the line-level script JSON and the review Markdown")
    _spec_arg(build)
    build.add_argument("--out", type=Path, help="script JSON path")
    build.add_argument("--markdown", type=Path, help="review Markdown path")
    build.set_defaults(func=cmd_build)

    estimate = actions.add_parser("estimate", help="print duration by segment")
    _spec_arg(estimate)
    estimate.set_defaults(func=cmd_estimate)

    breaks = actions.add_parser("breaks", help="suggest natural end points near a target duration")
    breaks.add_argument("spec", nargs="?", type=Path)
    breaks.add_argument("--section", type=int)
    breaks.add_argument("--target-seconds", type=float)
    breaks.add_argument("--narrator", default="sauti")
    breaks.add_argument("--start-paragraph", type=int, default=1)
    breaks.add_argument("--limit", type=int, default=5)
    breaks.set_defaults(func=cmd_breaks)

    render = actions.add_parser("render", help="synthesize lines with VoxCPM2, skipping cached lines")
    _spec_arg(render)
    render.add_argument("--dry-run", action="store_true")
    render.add_argument("--limit", type=int)
    render.set_defaults(func=cmd_render)

    assemble_p = actions.add_parser("assemble", help="join rendered lines, add gaps, normalize loudness")
    _spec_arg(assemble_p)
    assemble_p.add_argument("--out", type=Path)
    assemble_p.set_defaults(func=cmd_assemble)

    export = actions.add_parser("export-script", help="write the review Markdown")
    export.add_argument("spec", type=Path, help="episode YAML, or a script JSON to re-export")
    export.add_argument("--out", type=Path)
    export.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


def _spec_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("spec", type=Path, help="path to the episode YAML")


def cmd_build(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    script = build_episode(spec)
    json_path = args.out or spec.path.with_name(f"{spec.id}.script.json")
    md_path = args.markdown or spec.path.with_name(f"{spec.id}_script.md")
    _write_script(script, json_path, md_path)
    _print_summary(script)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    script = build_episode(spec)
    _print_summary(script)
    return 0


def cmd_breaks(args: argparse.Namespace) -> int:
    if args.section:
        target = args.target_seconds
        if target is None:
            print("--target-seconds is required with --section", file=sys.stderr)
            return 2
        suggestions = suggest_in_section(
            args.section, target, narrator=args.narrator, start_paragraph=args.start_paragraph, limit=args.limit,
        )
        _print_suggestions(suggestions, target)
        return 0
    if not args.spec:
        print("pass an episode YAML, or --section and --target-seconds", file=sys.stderr)
        return 2
    spec = load_spec(args.spec)
    report = suggest_for_spec(spec, limit=args.limit)
    print(f"prefix {report['prefix_s']:.0f} s · section {report.get('section')} target {report['section_target_s']:.0f} s")
    if report.get("chosen_paragraph"):
        print(f"spec currently ends at paragraph {report['chosen_paragraph']}")
    _print_suggestions(report["suggestions"], spec.target_duration_s)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    script = build_episode(spec)
    _timing, settings = load_timing(spec.timing_path)
    backend = VoxCPM2Backend()
    try:
        results = render_script(script, backend, settings, dry_run=args.dry_run, limit=args.limit)
    except ModuleNotFoundError as exc:
        print(f"VoxCPM2 is not installed in this interpreter ({exc}).", file=sys.stderr)
        print("Render with the prototype environment: MBH_VOX_PYTHON=proto/.venv-vox/bin/python", file=sys.stderr)
        return 1
    counts: dict[str, int] = {}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
        if item.status in {"missing_voice", "would_render", "rendered"}:
            print(f"{item.status}\t{item.line_id}\t{item.voice_id}")
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    manifest = spec.path.with_name(f"{spec.id}.render.json")
    if not args.dry_run:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps([item.to_dict() for item in results], indent=1), encoding="utf-8")
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    script = build_episode(spec)
    manifest = spec.path.with_name(f"{spec.id}.render.json")
    if not manifest.exists():
        print(f"no render manifest at {manifest}; run `mbh episode render` first", file=sys.stderr)
        return 1
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    results = [RenderResult(**row) for row in payload]
    timing, settings = load_timing(spec.timing_path)
    out = args.out or spec.path.with_name(f"{spec.id}.wav")
    try:
        report = assemble(script, results, timing, settings, out, intro=spec.intro, outro=spec.outro)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=1))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    path = args.spec
    if path.suffix == ".json":
        script = load_script(path)
        md_path = args.out or path.with_name(f"{script.episode_id}_script.md")
    else:
        spec = load_spec(path)
        script = build_episode(spec)
        md_path = args.out or spec.path.with_name(f"{spec.id}_script.md")
    md_path.write_text(render_markdown(script), encoding="utf-8")
    print(f"wrote {md_path}")
    return 0


def load_script(path: Path) -> EpisodeScript:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = []
    for row in data["lines"]:
        span = row.get("src_span")
        row = dict(row)
        row["src_span"] = tuple(span) if span else None
        lines.append(ScriptLine(**row))
    return EpisodeScript(
        episode_id=data["episode_id"],
        title=data["title"],
        book=data["book"],
        target_duration_s=data["target_duration_s"],
        estimated_duration_s=data["estimated_duration_s"],
        timing=data.get("timing") or {},
        lines=lines,
        warnings=list(data.get("warnings") or []),
        ending=dict(data.get("ending") or {}),
        generated_at=data.get("generated_at") or "",
        segments=list(data.get("segments") or []),
    )


def _write_script(script: EpisodeScript, json_path: Path, md_path: Path) -> None:
    json_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(script), encoding="utf-8")


def _print_summary(script: EpisodeScript) -> None:
    print(f"{script.episode_id}: {format_duration(script.estimated_duration_s)} "
          f"({script.estimated_duration_s:.1f} s), {len(script.lines)} lines, target {script.target_duration_s:.0f} s")
    by_seg: dict[str, list] = {}
    for line in script.lines:
        by_seg.setdefault(line.segment_id, []).append(line)
    for seg_id, seg_lines in by_seg.items():
        start = seg_lines[0].start_s
        end = seg_lines[-1].start_s + seg_lines[-1].duration_s
        print(f"  {seg_id}: {end - start:.1f} s, {len(seg_lines)} lines, §{seg_lines[0].section} ¶{seg_lines[0].paragraph}")
    if script.warnings:
        print(f"  warnings: {len(script.warnings)}")
        for warning in script.warnings[:8]:
            print(f"  - {warning}")


def _print_suggestions(suggestions, target: float) -> None:
    if not suggestions:
        print("no legal break points")
        return
    print(f"target {target:.0f} s")
    for item in suggestions:
        where = f"§{item.section} ¶{item.paragraph}" if item.section else item.line_id
        print(f"  {item.at_s:6.1f}s  {item.delta_s:+6.1f}s  {where}  score {item.score:.0f}")
        print(f"    {'; '.join(item.reasons)}")
        print(f"    {item.text[:140]}")


if __name__ == "__main__":
    raise SystemExit(main())
