"""Headless UI end-to-end test + screenshots against a running server (default http://localhost:8765).
usage: .venv/bin/python tests/e2e_ui.py [base_url]"""
import sys, json, time, urllib.request
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
def api(path, method="GET"):
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + path, method=method)).read() or "null")
ok = lambda m: print("PASS", m)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    pg = b.new_page(viewport={"width": 1600, "height": 950}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto(BASE + "/"); pg.wait_for_function("typeof cy !== 'undefined' && cy.nodes && cy.nodes().length > 80"); time.sleep(1)
    n = pg.evaluate("cy.nodes().length"); e = pg.evaluate("cy.edges().length"); ok(f"graph rendered: {n} nodes, {e} edges")
    pg.screenshot(path="screens/01_graph.png")
    # select Bhishma via graph tap
    pg.evaluate("cy.$id('bhishma').emit('tap')"); pg.wait_for_selector("#detail:not([hidden])"); time.sleep(0.8)
    assert pg.input_value("#fProfile [name=name]") == "Bhishma"; ok("node tap opens profile")
    pg.screenshot(path="screens/02_bhishma_profile.png")
    pg.click(".tabs button[data-tab=voice]"); time.sleep(0.5)
    assert pg.locator("#vClip audio").count() == 1; ok("voice tab shows reference audio player")
    src = pg.get_attribute("#vClip audio", "src"); assert urllib.request.urlopen(BASE + src).status == 200; ok("reference clip URL serves audio")
    pg.screenshot(path="screens/03_bhishma_voice.png")
    pg.click(".tabs button[data-tab=rels]"); time.sleep(0.3); pg.screenshot(path="screens/04_bhishma_relationships.png")
    # CREATE character via dialog
    pg.click("#btnNew"); pg.fill("#fNew [name=name]", "Kindama Test"); pg.fill("#fNew [name=gender]", "male"); pg.click("#fNew button[value=ok]")
    pg.wait_for_function("document.querySelector('#dName').textContent==='Kindama Test'"); assert api("/api/characters/kindama_test")["gender"] == "male"; ok("create character via UI")
    # UPDATE profile
    pg.click(".tabs button[data-tab=profile]"); pg.fill("#fProfile [name=respelling]", "KIN-duh-muh"); pg.fill("#fProfile [name=personality]", "wounded, wrathful")
    pg.click("#fProfile button[type=submit]"); time.sleep(0.8)
    c = api("/api/characters/kindama_test"); assert c["respelling"] == "KIN-duh-muh" and c["personality"] == ["wounded", "wrathful"]; ok("update character via UI")
    # CREATE relationship inline (Kindama cursed Pandu)
    pg.click(".tabs button[data-tab=rels]"); pg.select_option("#fRelInline [name=type]", "cursed"); pg.fill("#fRelInline [name=other]", "pandu"); pg.click("#fRelInline button")
    time.sleep(0.8); rels = api("/api/relationships?character=kindama_test"); assert any(r["target"] == "pandu" and r["type"] == "cursed" for r in rels); ok("create relationship via UI")
    assert pg.evaluate("cy.edges().filter(e=>e.data('source')==='kindama_test').length") == 1; ok("graph updated with new edge")
    # DELETE relationship via UI
    pg.click("#relBody button[data-del]"); time.sleep(0.8); assert api("/api/relationships?character=kindama_test") == []; ok("delete relationship via UI")
    # DELETE character via UI
    pg.click(".tabs button[data-tab=profile]"); pg.click("#btnDelete"); time.sleep(0.8)
    try: api("/api/characters/kindama_test"); raise AssertionError("still exists")
    except urllib.error.HTTPError as ex: assert ex.code == 404
    ok("delete character via UI")
    # filters + table
    pg.fill("#search", "Kuru"); time.sleep(0.3); vis = pg.evaluate("cy.nodes().filter(n=>n.style('display')!=='none').length"); ok(f"search filter 'Kuru' -> {vis} visible nodes"); pg.fill("#search", "")
    assert not errors, errors; pg.close()
    # fresh page for the screenshot tour (long headless sessions occasionally crash the renderer on this box)
    pg = b.new_page(viewport={"width": 1600, "height": 950}); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/"); pg.wait_for_function("typeof cy !== 'undefined' && cy.nodes && cy.nodes().length > 80"); time.sleep(1)
    pg.uncheck("#legend input[data-type=parent_of]"); time.sleep(0.2); print("step shot5", flush=True); pg.screenshot(path="screens/05_graph_without_parent_edges.png"); pg.check("#legend input[data-type=parent_of]")
    pg.evaluate("cy.$id('arjuna').emit('tap')"); time.sleep(0.8); pg.screenshot(path="screens/06_arjuna_neighbourhood.png")
    pg.click("#btnView"); time.sleep(0.5); pg.screenshot(path="screens/07_table_view.png"); pg.click("#btnView")
    pg.evaluate("cy.$id('drona').emit('tap')"); time.sleep(0.8); pg.click(".tabs button[data-tab=voice]"); time.sleep(0.8); pg.screenshot(path="screens/08_drona_generated_candidate.png")
    pg.close(); pg = b.new_page(viewport={"width": 1600, "height": 950}); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/"); pg.wait_for_function("typeof cy !== 'undefined' && cy.nodes && cy.nodes().length > 80"); time.sleep(1)
    pg.evaluate("cy.$id('hidimbi').emit('tap')"); time.sleep(0.8); pg.click(".tabs button[data-tab=profile]"); time.sleep(0.3)
    assert "text-extracted" in pg.inner_text("#dBadges"); ok("provenance badge shown"); pg.screenshot(path="screens/09_hidimbi_extracted_profile.png")
    pg.evaluate("cy.$id('vishnu').emit('tap')"); time.sleep(0.8); pg.click(".tabs button[data-tab=rels]"); time.sleep(0.3)
    assert "incarnation of" in pg.inner_text("#relBody"); ok("new relation types rendered"); pg.screenshot(path="screens/10_vishnu_incarnations.png")
    pg.evaluate("cy.$id('satasringa_rishis').emit('tap')"); time.sleep(0.8); pg.click(".tabs button[data-tab=voice]"); time.sleep(0.5)
    assert "Rishis of Naimisha" in pg.inner_text("#vNotes"); ok("shared group voice shown"); pg.screenshot(path="screens/11_satasringa_shared_group_voice.png")
    assert not errors, errors; ok("no JS errors")
    b.close()
print("ALL UI CHECKS PASSED")
