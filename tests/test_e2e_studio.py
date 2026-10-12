"""Headless Episode Studio smoke test. Skips when Playwright or Chrome is missing.

Drives the browser the way a person would: estimate, breaks, create, edit a line,
mock-render, assemble, play, lexicon, voice design, jobs. Screenshots land in
screens/studio/.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHROME = "/usr/bin/google-chrome"
SHOTS = ROOT / "screens" / "studio"

pytest.importorskip("playwright")
if not Path(CHROME).exists():
    pytest.skip("google-chrome is not installed", allow_module_level=True)

from playwright.sync_api import sync_playwright


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _post(base: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="POST")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise AssertionError(exc.read().decode()) from exc


def _wait_job(base: str, jid: int, timeout: float = 60):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = _get(base, f"/api/jobs/{jid}")
        if last["status"] in {"done", "failed", "cancelled"}:
            return last
        time.sleep(0.2)
    raise AssertionError(last)


def _wait_kind(base: str, kind: str, timeout: float = 30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = _get(base, f"/api/jobs?kind={kind}&limit=1")
        if rows:
            return _wait_job(base, rows[0]["id"], timeout=max(5, deadline - time.time()))
        time.sleep(0.15)
    raise AssertionError(f"no {kind} job")


def _click_job(page, base: str, action: str, kind: str):
    """Click a script-page button and wait until a new job of that kind finishes."""
    before = {row["id"] for row in _get(base, f"/api/jobs?kind={kind}&limit=20")}
    page.wait_for_selector(f"[data-action={action}]")
    page.click(f"[data-action={action}]")
    deadline = time.time() + 20
    fresh = None
    while time.time() < deadline:
        rows = _get(base, f"/api/jobs?kind={kind}&limit=5")
        found = [row for row in rows if row["id"] not in before]
        if found:
            fresh = found[0]
            break
        time.sleep(0.15)
    if fresh is None:
        page.screenshot(path=str(SHOTS / "fail_click.png"))
        raise AssertionError(f"click {action} did not queue {kind}: {page.inner_text('body')[:800]}")
    return _wait_job(base, fresh["id"])


@pytest.fixture(scope="module")
def studio_server():
    tmp = Path(tempfile.mkdtemp(prefix="mbh-e2e-studio-"))
    (tmp / "episodes").mkdir()
    shutil.copy(ROOT / "lexicon" / "book01.tsv", tmp / "lexicon.tsv")
    port = _free_port()
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT / "src"),
        "MBH_STUDIO_MOCK": "1",
        "MBH_DB": str(tmp / "studio.sqlite3"),
        "MBH_EPISODES": str(tmp / "episodes"),
        "MBH_LEXICON": str(tmp / "lexicon.tsv"),
        "MBH_BUILD": str(tmp / "build"),
        "MBH_HOST": "127.0.0.1",
        "MBH_PORT": str(port),
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "mbh.webapp"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    up = False
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(proc.stdout.read() if proc.stdout else "server exited")
        try:
            _get(base, "/api/studio/meta")
            up = True
            break
        except Exception:
            time.sleep(0.2)
    if not up:
        proc.kill()
        raise RuntimeError("studio server did not start")
    try:
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


def test_studio_ui_flow(studio_server):
    base = studio_server
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME, headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(base + "/studio#/episodes")
        page.wait_for_selector("h1")
        assert "Episodes" in page.inner_text("h1")
        page.screenshot(path=str(SHOTS / "01_episodes.png"))

        page.goto(base + "/studio#/new")
        page.wait_for_selector("#ep-id")
        page.fill("#ep-id", "ep_smoke")
        page.fill("#ep-title", "Smoke episode")
        page.fill("#target-min", "2")
        page.uncheck("#music-on")
        page.fill("#seg-section", "1")
        page.fill("#seg-start", "1")
        page.fill("#seg-end", "2")
        page.fill("#bridge-text", "This bridge is not in the KMG translation.")
        page.fill("#end-reason", "Smoke-test ending.")
        page.click("[data-action=estimate]")
        page.wait_for_selector("#estimate b")
        assert "estimated" in page.inner_text("#estimate")
        page.click("[data-action=breaks]")
        page.wait_for_selector("#breaks button, #breaks .note")
        assert page.locator("#breaks").inner_text().strip()
        near = page.locator("#breaks button[data-para='1'], #breaks button[data-para='2']")
        if near.count():
            near.first.click()
        page.screenshot(path=str(SHOTS / "02_new_episode.png"))
        page.click("[data-action=create]")
        page.wait_for_selector("#script-table tr[data-line]")
        assert page.locator("tr.nonkmg").count() >= 1
        assert "non-KMG" in page.inner_text("#script-table")
        row = page.locator("#script-table tr[data-line]").nth(1)
        row.locator(".emotion").select_option("commanding")
        row.locator("[data-action=save]").click()
        page.wait_for_selector("#script-table .badge")
        page.screenshot(path=str(SHOTS / "03_script.png"))

        render_job = _click_job(page, base, "render", "render")
        assert render_job["status"] == "done", render_job
        page.wait_for_selector("#script-table audio")
        page.screenshot(path=str(SHOTS / "04_script_rendered.png"))

        assembled = _click_job(page, base, "assemble", "assemble")
        assert assembled["status"] == "done", assembled
        qa_job = _click_job(page, base, "qa", "qa")
        assert qa_job["status"] == "done", qa_job

        page.goto(base + "/studio#/e/ep_smoke/play")
        page.wait_for_selector("#wave")
        page.wait_for_selector("#player-lines button")
        page.locator("#player-lines button").first.click()
        page.wait_for_function("() => document.querySelector('#player').currentTime >= 0")
        assert page.locator("#player-lines .badge.warn").count() >= 1
        page.screenshot(path=str(SHOTS / "05_player.png"))

        page.goto(base + "/studio#/lexicon?q=Naimisha")
        page.wait_for_selector("#lex-table tr[data-term='Naimisha']")
        lex = page.locator("#lex-table tr[data-term='Naimisha']")
        lex.locator(".notes").fill("studio smoke")
        with page.expect_response(lambda resp: resp.request.method == "PUT" and "/api/studio/lexicon" in resp.url):
            lex.locator("[data-action=save]").click()
        saved = _get(base, "/api/studio/lexicon?q=Naimisha")
        assert saved[0]["notes"] == "studio smoke"
        page.click("#lex-table tr[data-term='Naimisha'] [data-action=test]")
        page.wait_for_selector("#pron audio", timeout=20000)
        page.screenshot(path=str(SHOTS / "06_lexicon.png"))

        _post(base, "/api/characters", {
            "name": "Studio Smoke",
            "voice_brief": "A clear aged sage, Indian English accent",
            "sample_line": "Hear this voice.",
        })
        page.goto(base + "/studio#/voices/studio_smoke")
        page.wait_for_selector("[data-voice=studio_smoke]")
        page.click("[data-voice=studio_smoke] [data-action=design]")
        designed = _wait_kind(base, "design_voice")
        assert designed["status"] == "done", designed
        page.wait_for_selector("[data-voice=studio_smoke] .cand audio", timeout=15000)
        page.click("[data-voice=studio_smoke] [data-file]")
        page.wait_for_selector("[data-voice=studio_smoke] audio[src*='ref.wav']")
        page.screenshot(path=str(SHOTS / "07_voices.png"))

        page.goto(base + "/studio#/jobs")
        page.wait_for_selector("article.job")
        assert "done" in page.inner_text("#view")
        page.screenshot(path=str(SHOTS / "08_jobs.png"))

        page.goto(base + "/")
        page.wait_for_selector(".appnav a[href='/studio']")
        page.screenshot(path=str(SHOTS / "09_map_nav.png"))

        assert not errors, errors
        browser.close()

    req = urllib.request.Request(base + "/api/characters/studio_smoke?delete_voice_files=true", method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
