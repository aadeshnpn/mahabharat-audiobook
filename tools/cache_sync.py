#!/usr/bin/env python3
"""Render-cache sync: keep rendered lines and song takes off the box (stdlib only; any python3 works).

Where:  GitHub release assets on the pre-release tag ``render-cache`` (public download URLs, no token to pull), and a
        mirror in the persistent agent store (survives box cleaning).
What:   files under CACHE_GLOBS (per-line episode cache, song/title takes), packed into tar.gz chunks of <= 50 MB,
        grouped per episode (via episodes/*.render.json) or per song, plus ``manifest.json``:
        {"files": {relpath: {sha256, size, chunk}}, "chunks": {name: {sha256, size, group, files}}}.
        Chunk names are content-addressed (<group>-<hash12>.tar.gz), so a push only ever adds chunks.

usage:
  tools/cache_sync.py status                 local files vs the remote (or --from-dir) manifest
  tools/cache_sync.py pull [--from-dir DIR]  download + unpack missing files (remote release, or an export/store dir)
  tools/cache_sync.py push [--export DIR]    pack new/changed files; upload with gh (GITHUB_TOKEN/GH_TOKEN or gh auth),
                                             or with --export write chunks + manifest.json to DIR for someone to upload
  tools/cache_sync.py backup [--store DIR]   mirror cache files into the persistent store (default $MBH_CACHE_STORE)
"""
from __future__ import annotations

import argparse, glob, hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "render-cache"
CHUNK_LIMIT = 50 * 1000 * 1000
CACHE_GLOBS = ["build/cache/*/*.wav", "build/song/*/takes/*.wav", "build/title_song_v5/takes/*.wav"]
DEFAULT_STORE = "/cursor/stores/store-36ba7fba-4e2b-4fb7-b9e4-dfc8c8df42c1/mahabharat-cache"
REPO = "aadeshnpn/mahabharat-audiobook"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def local_files(root: Path = ROOT, globs=CACHE_GLOBS) -> dict[str, Path]:
    out = {}
    for g in globs:
        for p in sorted(glob.glob(str(root / g))):
            p = Path(p)
            if p.is_file() and p.stat().st_size:
                out[p.relative_to(root).as_posix()] = p
    return out


def episode_of(root: Path = ROOT) -> dict[str, str]:
    """cache wav name -> episode id, from render manifests (episodes/<id>.render.json) when present."""
    m = {}
    for man in sorted((root / "episodes").glob("*.render.json")):
        try:
            for row in json.loads(man.read_text()):
                if row.get("cache_key"):
                    m.setdefault(f"{row['cache_key']}.wav", man.name[: -len(".render.json")])
        except (ValueError, TypeError):
            continue
    return m


def group_of(rel: str, eps: dict[str, str]) -> str:
    parts = rel.split("/")
    if parts[1] == "cache":
        return eps.get(parts[-1], "lines")
    if parts[1] == "song":
        return f"song-{parts[2]}"
    return parts[1].replace("_", "-")


def empty_manifest() -> dict:
    return {"version": 1, "tag": TAG, "files": {}, "chunks": {}}


def pack(files: dict[str, Path], base: dict, out_dir: Path, root: Path = ROOT, limit: int = CHUNK_LIMIT) -> dict:
    """Pack files that are new or changed vs ``base`` into chunks in ``out_dir``; return the merged manifest."""
    man = json.loads(json.dumps(base or empty_manifest()))
    eps = episode_of(root); todo: dict[str, list] = {}
    for rel, p in files.items():
        h = sha256(p)
        if man["files"].get(rel, {}).get("sha256") == h:
            continue
        todo.setdefault(group_of(rel, eps), []).append((rel, p, h))
    out_dir.mkdir(parents=True, exist_ok=True)
    for group, items in sorted(todo.items()):
        batch, size = [], 0
        for item in items + [None]:
            if item is not None and (not batch or size + item[1].stat().st_size + 1024 <= limit):
                batch.append(item); size += item[1].stat().st_size + 1024
                continue
            if batch:
                ident = hashlib.sha256("".join(f"{r}{h}" for r, _, h in batch).encode()).hexdigest()[:12]
                name = f"{group}-{ident}.tar.gz"; path = out_dir / name
                with tarfile.open(path, "w:gz", compresslevel=6) as tar:
                    for rel, p, _h in batch:
                        tar.add(p, arcname=rel)
                man["chunks"][name] = {"sha256": sha256(path), "size": path.stat().st_size, "group": group, "files": len(batch)}
                for rel, p, h in batch:
                    man["files"][rel] = {"sha256": h, "size": p.stat().st_size, "chunk": name}
            if item is not None:
                batch, size = [item], item[1].stat().st_size + 1024
    (out_dir / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    return man


def _fetch(src: str, name: str) -> bytes:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(f"{src}/{name}", timeout=120) as r:
            return r.read()
    return (Path(src) / name).read_bytes()


def release_url(repo: str = REPO) -> str:
    return f"https://github.com/{repo}/releases/download/{TAG}"


def read_manifest(src: str) -> dict | None:
    try:
        return json.loads(_fetch(src, "manifest.json"))
    except Exception as exc:  # offline, no release yet, or no such dir
        print(f"no manifest at {src}: {exc}", file=sys.stderr)
        return None


def pull(src: str, root: Path = ROOT) -> dict:
    man = read_manifest(src)
    if man is None:
        return {"pulled": 0, "error": "no manifest"}
    need = {}
    for rel, f in man["files"].items():
        p = root / rel
        if not (p.exists() and p.stat().st_size == f["size"]):
            need.setdefault(f["chunk"], []).append(rel)
    got = bad = 0
    for chunk, rels in sorted(need.items()):
        data = _fetch(src, chunk)
        if hashlib.sha256(data).hexdigest() != man["chunks"][chunk]["sha256"]:
            print(f"checksum mismatch: {chunk}", file=sys.stderr); bad += 1; continue
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for m in tar.getmembers():
                if m.name in rels and m.isfile() and not m.name.startswith(("/", "..")) and ".." not in m.name.split("/"):
                    dest = root / m.name; dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    tmp.write_bytes(tar.extractfile(m).read())
                    if sha256(tmp) == man["files"][m.name]["sha256"]:
                        tmp.replace(dest); got += 1
                    else:
                        tmp.unlink(); bad += 1
    return {"pulled": got, "chunks": len(need), "bad": bad, "known": len(man["files"])}


def push(export: Path | None, base_src: str | None, root: Path = ROOT) -> dict:
    base = read_manifest(base_src) if base_src else None
    files = local_files(root)
    if export:
        man = pack(files, base, export, root)
        new = [c for c in man["chunks"] if not (base and c in base["chunks"])]
        for c in list(export.glob("*.tar.gz")):
            if c.name not in new:
                c.unlink()  # export holds only what must be uploaded (plus the merged manifest)
        return {"export": str(export), "new_chunks": new, "files": len(man["files"])}
    if not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or
            subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0):
        raise SystemExit("push needs gh auth or GITHUB_TOKEN; use `push --export DIR` and upload DIR elsewhere")
    with tempfile.TemporaryDirectory() as d:
        r = push(Path(d), base_src, root)
        upload(Path(d)); return r


def upload(d: Path, repo: str = REPO) -> None:
    """Upload an export dir to the render-cache release (creates the pre-release if needed)."""
    if subprocess.run(["gh", "release", "view", TAG, "-R", repo], capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", TAG, "-R", repo, "--prerelease", "--title", "Render cache",
                        "--notes", "Per-line render cache chunks (tools/cache_sync.py). Not a release."], check=True)
    chunks = sorted(str(p) for p in d.glob("*.tar.gz"))
    if chunks:
        subprocess.run(["gh", "release", "upload", TAG, "-R", repo, *chunks], check=True)
    subprocess.run(["gh", "release", "upload", TAG, "-R", repo, str(d / "manifest.json"), "--clobber"], check=True)


def backup(store: Path, root: Path = ROOT) -> dict:
    """Mirror cache files into the persistent store (copy when missing or size differs)."""
    copied = 0
    for rel, p in local_files(root).items():
        dest = store / rel
        if dest.exists() and dest.stat().st_size == p.stat().st_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True); tmp = dest.with_suffix(dest.suffix + ".part")
        shutil.copyfile(p, tmp); tmp.replace(dest); copied += 1
    return {"store": str(store), "copied": copied, "total": len(local_files(store))}


def restore_from_store(store: Path, root: Path = ROOT) -> dict:
    n = 0
    for rel, p in local_files(store).items():
        dest = root / rel
        if not (dest.exists() and dest.stat().st_size == p.stat().st_size):
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest); n += 1
    return {"restored": n, "store": str(store)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "pull", "push", "backup", "restore"])
    ap.add_argument("--from-dir", help="pull/status from an export dir instead of the GitHub release")
    ap.add_argument("--export", type=Path, help="push: write chunks + manifest here instead of uploading")
    ap.add_argument("--base", help="push: manifest source to diff against (release URL or dir; default the release)")
    ap.add_argument("--store", type=Path, default=Path(os.environ.get("MBH_CACHE_STORE", DEFAULT_STORE)))
    a = ap.parse_args(argv)
    src = a.from_dir or release_url()
    if a.cmd == "status":
        man = read_manifest(src) or empty_manifest(); loc = local_files()
        print(json.dumps({"local": len(loc), "remote": len(man["files"]),
                          "remote_only": len(set(man["files"]) - set(loc)), "local_only": len(set(loc) - set(man["files"]))}))
    elif a.cmd == "pull":
        print(json.dumps(pull(src)))
    elif a.cmd == "push":
        print(json.dumps(push(a.export, a.base or src)))
    elif a.cmd == "backup":
        if not a.store.parent.exists():
            print(json.dumps({"store": str(a.store), "skipped": "store not mounted"})); return 0
        print(json.dumps(backup(a.store)))
    elif a.cmd == "restore":
        print(json.dumps(restore_from_store(a.store)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
