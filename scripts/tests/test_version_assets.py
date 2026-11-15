"""version_assets.py: every module URL and page asset gets the deploy version."""
from version_assets import stamp_html, stamp_js


def test_relative_imports_are_stamped():
    js = 'import { map } from "./map.js";\nimport { CONFIG } from "../config.js";\nconst m = await import("./alerts.js");'
    out = stamp_js(js, "abc123")
    assert '"./map.js?v=abc123"' in out
    assert '"../config.js?v=abc123"' in out
    assert 'import("./alerts.js?v=abc123")' in out


def test_bare_and_remote_imports_are_left_alone():
    js = 'import x from "https://cdn.example/x.js";\nconst s = "./not-an-import.js";'
    assert stamp_js(js, "v1") == js


def test_index_scripts_and_styles_are_stamped_but_not_data_or_remote():
    html = ('<script type="module" src="app.js"></script><link rel="modulepreload" href="layers/loader.js">'
            '<link rel="stylesheet" href="style.css"><link rel="preload" href="data/episodes.json" as="fetch">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow">')
    out = stamp_html(html, "v1")
    assert 'src="app.js?v=v1"' in out and 'href="layers/loader.js?v=v1"' in out and 'href="style.css?v=v1"' in out
    assert 'href="data/episodes.json"' in out and "fonts.googleapis.com/css2?family=Barlow" in out
