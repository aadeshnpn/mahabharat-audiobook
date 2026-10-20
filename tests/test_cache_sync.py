import importlib.util, json, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("cache_sync", Path(__file__).resolve().parents[1] / "tools/cache_sync.py")
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)


def _repo(tmp: Path, n=5, size=3000):
    (tmp / "episodes").mkdir(parents=True)
    d = tmp / "build/cache/voxcpm2"; d.mkdir(parents=True)
    rows = []
    for i in range(n):
        (d / f"k{i}.wav").write_bytes(bytes([i]) * size); rows.append({"cache_key": f"k{i}"})
    (tmp / "episodes/ep09.render.json").write_text(json.dumps(rows[:3]))
    t = tmp / "build/song/demo/takes"; t.mkdir(parents=True); (t / "a.wav").write_bytes(b"x" * 100)
    return tmp


def test_pack_groups_limits_and_roundtrip(tmp_path):
    root = _repo(tmp_path / "src")
    man = cs.pack(cs.local_files(root), None, tmp_path / "out", root, limit=8000)
    groups = {c["group"] for c in man["chunks"].values()}
    assert groups == {"ep09", "lines", "song-demo"}
    assert all(c["size"] <= 8000 + 2000 for c in man["chunks"].values())     # 2 lines per chunk at most
    assert len(man["files"]) == 6
    dst = tmp_path / "dst"; dst.mkdir()
    r = cs.pull(str(tmp_path / "out"), dst)
    assert r["pulled"] == 6 and r["bad"] == 0
    assert (dst / "build/cache/voxcpm2/k4.wav").read_bytes() == bytes([4]) * 3000
    assert cs.pull(str(tmp_path / "out"), dst)["pulled"] == 0                  # nothing missing now


def test_push_export_is_incremental(tmp_path):
    root = _repo(tmp_path / "src")
    first = tmp_path / "e1"; cs.push(first, None, root)
    (root / "build/cache/voxcpm2/new.wav").write_bytes(b"n" * 50)
    second = tmp_path / "e2"; r = cs.push(second, str(first), root)
    assert len(r["new_chunks"]) == 1 and r["files"] == 7
    assert [p.name for p in second.glob("*.tar.gz")] == r["new_chunks"]
    man = json.loads((second / "manifest.json").read_text())
    assert man["files"]["build/cache/voxcpm2/new.wav"]["chunk"] == r["new_chunks"][0]


def test_backup_and_restore(tmp_path):
    root = _repo(tmp_path / "src"); store = tmp_path / "store"
    assert cs.backup(store, root)["copied"] == 6
    assert cs.backup(store, root)["copied"] == 0
    dst = tmp_path / "dst"; assert cs.restore_from_store(store, dst)["restored"] == 6
