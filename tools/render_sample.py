"""Render and assemble a short excerpt of an episode (same line cache, music preset) for review.
usage (proto/.venv-vox): PYTHONPATH=src python tools/render_sample.py episodes/ep04.yaml FIRST_ID LAST_ID OUT.wav [preset=A] [--intro] [--outro]
       or pick lines:   ... tools/render_sample.py episodes/ep05.yaml ID1,ID2,ID3 - OUT.wav [preset] [--intro]
--intro / --outro add the episode's intro/outro (e.g. the v6 sting title) with its crossfade, as in the full episode."""
import dataclasses, json, sys
from pathlib import Path
from mbh.cli import _music_cfg
from mbh.episode.assemble import assemble
from mbh.episode.build import build_episode
from mbh.episode.render import VoxCPM2Backend, render_script
from mbh.episode.spec import load_spec
from mbh.episode.timing import load_timing
flags = {a for a in sys.argv[1:] if a.startswith("--")}; argv = [a for a in sys.argv if not a.startswith("--")]
spec = load_spec(Path(argv[1])); first, last, out = argv[2], argv[3], Path(argv[4])
preset = argv[5] if len(argv) > 5 else "A"
script = build_episode(spec); ids = [l.id for l in script.lines]
keep = first.split(",") if "," in first or last == "-" else ids[ids.index(first): ids.index(last) + 1]
hooks = {}
if "--intro" in flags and spec.intro:
    hooks.update(intro=spec.intro, intro_crossfade_s=spec.intro_crossfade_s)
if "--outro" in flags and spec.outro:
    hooks.update(outro=spec.outro, outro_crossfade_s=spec.outro_crossfade_s)
timing, settings = load_timing(spec.timing_path)
results = render_script(script, VoxCPM2Backend(), settings, only=set(keep))
part = dataclasses.replace(script, lines=[l for l in script.lines if l.id in set(keep)])
results = [r for r in results if r.line_id in set(keep)]
print(json.dumps({k: v for k, v in assemble(part, results, timing, settings, out, **hooks,
      music_cfg=_music_cfg(spec.music or True, None, preset, spec.music_rules)).items() if not isinstance(v, (list, dict))}))
print("SAMPLE_DONE")
