"""Render and assemble a short excerpt of an episode (same line cache, music preset) for review.
usage (proto/.venv-vox): PYTHONPATH=src python tools/render_sample.py episodes/ep04.yaml FIRST_ID LAST_ID OUT.wav [preset=A]"""
import dataclasses, json, sys
from pathlib import Path
from mbh.cli import _music_cfg
from mbh.episode.assemble import assemble
from mbh.episode.build import build_episode
from mbh.episode.render import VoxCPM2Backend, render_script
from mbh.episode.spec import load_spec
from mbh.episode.timing import load_timing
spec = load_spec(Path(sys.argv[1])); first, last, out = sys.argv[2], sys.argv[3], Path(sys.argv[4])
preset = sys.argv[5] if len(sys.argv) > 5 else "A"
script = build_episode(spec); ids = [l.id for l in script.lines]
keep = ids[ids.index(first): ids.index(last) + 1]
timing, settings = load_timing(spec.timing_path)
results = render_script(script, VoxCPM2Backend(), settings, only=set(keep))
part = dataclasses.replace(script, lines=[l for l in script.lines if l.id in set(keep)])
results = [r for r in results if r.line_id in set(keep)]
print(json.dumps({k: v for k, v in assemble(part, results, timing, settings, out,
      music_cfg=_music_cfg(spec.music or True, None, preset, spec.music_rules)).items() if not isinstance(v, (list, dict))}))
print("SAMPLE_DONE")
