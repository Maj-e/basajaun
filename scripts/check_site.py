"""End-to-end check of the published site (W2-B4).

Downloads, from the live URL, everything the page needs for its data:
    - the data files named in the published config.js (manifest, daily summary, land outline…)
    - every file listed in the published manifest.json
    - if data/episodes.json is published: every episode's manifest and the files it lists
validates each one against the contract (same rules as validate.py) and times the first page load.

Fails (exit 1) if any file is missing, broken or off-contract, or if the first page load
is slower than the budget.

Usage:
    uv run scripts/check_site.py                       # default URL (SITE_URL env or GitHub Pages)
    uv run scripts/check_site.py --url http://localhost:8000/ --max-load 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import requests

import validate

DEFAULT_URL = os.getenv("SITE_URL", "https://maj-e.github.io/ulinautas/")
DEFAULT_MAX_LOAD_S = float(os.getenv("MAX_LOAD_S", "10"))
TIMEOUT_S = 30
RETRIES = 3
RETRY_WAIT_S = 5

# Data paths written in config.js, e.g.  manifest: "data/manifest.json"
CONFIG_DATA_PATH = re.compile(r"""["'](data/[^"']+\.(?:json|geojson|png))["']""")


@dataclass
class FileResult:
    path: str                  # relative to the site root, e.g. data/manifest.json
    first_load: bool           # fetched by the page on its first load
    status: int | None = None  # HTTP status, None if the request itself failed
    size: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class Report:
    url: str
    max_load_s: float
    files: list[FileResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # site-level errors
    notes: list[str] = field(default_factory=list)   # informative, never fail the check

    @property
    def first_load_seconds(self) -> float:
        return sum(f.seconds for f in self.files if f.first_load)

    @property
    def first_load_bytes(self) -> int:
        return sum(f.size for f in self.files if f.first_load)

    @property
    def ok(self) -> bool:
        return not self.errors and all(not f.errors for f in self.files)


def fetch(session: requests.Session, url: str, buster: str) -> tuple[requests.Response | None, float, str | None]:
    """GET with a cache-busting query and a few retries. Returns (response, seconds, error)."""
    last_error = None
    for attempt in range(RETRIES):
        start = time.perf_counter()
        try:
            resp = session.get(url, params={"e2e": buster}, timeout=TIMEOUT_S,
                               headers={"Cache-Control": "no-cache"})
            elapsed = time.perf_counter() - start
            if resp.status_code < 500:
                return resp, elapsed, None
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = f"request failed: {exc.__class__.__name__}"
        if attempt < RETRIES - 1:
            time.sleep(RETRY_WAIT_S)
    return None, 0.0, last_error


def download(session, base_url, rel_path, dest_root: Path, buster, first_load) -> FileResult:
    result = FileResult(path=rel_path, first_load=first_load)
    resp, result.seconds, error = fetch(session, urljoin(base_url, rel_path), buster)
    if resp is None:
        result.errors.append(error)
        return result
    result.status, result.size = resp.status_code, len(resp.content)
    if resp.status_code != 200:
        result.errors.append(f"HTTP {resp.status_code} (missing on the site)")
        return result
    target = dest_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(resp.content)
    return result


def check_site(base_url: str = DEFAULT_URL, max_load_s: float = DEFAULT_MAX_LOAD_S,
               session: requests.Session | None = None) -> Report:
    base_url = base_url if base_url.endswith("/") else base_url + "/"
    session = session or requests.Session()
    buster = str(int(time.time()))
    report = Report(url=base_url, max_load_s=max_load_s)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 1. Page shell + config.js: tells us which data files the page loads first
        for shell in ("index.html", "config.js"):
            report.files.append(download(session, base_url, shell, root, buster, first_load=True))
        config_js = root / "config.js"
        config_paths = sorted(set(CONFIG_DATA_PATH.findall(config_js.read_text(encoding="utf-8")))) if config_js.is_file() else []
        manifest_path = "data/manifest.json"
        if manifest_path not in config_paths:
            config_paths.insert(0, manifest_path)
        for rel in config_paths:
            report.files.append(download(session, base_url, rel, root, buster, first_load=True))

        # 2. Every layer file listed in the published manifest (active layers load on first paint)
        manifest_file = root / manifest_path
        manifest = None
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass  # reported by the contract validation below
        if isinstance(manifest, dict):
            already = {f.path for f in report.files}
            for layer in manifest.get("layers", []):
                rel = f"data/{layer.get('file', '')}"
                if rel not in already:
                    report.files.append(download(session, base_url, rel, root, buster,
                                                 first_load=bool(layer.get("active"))))
                    already.add(rel)

        # 2b. Other episodes (W4-B5): their manifests and layer files, not part of the first load
        episodes_path = "data/episodes.json"
        resp, _, _ = fetch(session, urljoin(base_url, episodes_path), buster)
        if resp is not None and resp.status_code == 200:
            report.files.append(download(session, base_url, episodes_path, root, buster, first_load=False))
            try:
                episodes = json.loads((root / episodes_path).read_text(encoding="utf-8")).get("episodes", [])
            except (json.JSONDecodeError, AttributeError, FileNotFoundError):
                episodes = []  # reported by the contract validation below
            already = {f.path for f in report.files}
            for episode in episodes:
                ep_manifest = f"data/{episode.get('manifest', '')}"
                if episode.get("live") and ep_manifest not in already:
                    probe, _, _ = fetch(session, urljoin(base_url, ep_manifest), buster)
                    if probe is None or probe.status_code != 200:
                        # Right after a deploy from main, update-data.yml hasn't published live/ yet
                        report.notes.append(f"live episode '{episode.get('id')}' not published yet")
                        continue
                if ep_manifest not in already:
                    report.files.append(download(session, base_url, ep_manifest, root, buster, first_load=False))
                    already.add(ep_manifest)
                try:
                    layers = json.loads((root / ep_manifest).read_text(encoding="utf-8")).get("layers", [])
                except (json.JSONDecodeError, AttributeError, FileNotFoundError, IsADirectoryError):
                    layers = []
                for layer in layers:
                    rel = f"data/{layer.get('file', '')}"
                    if rel not in already:
                        report.files.append(download(session, base_url, rel, root, buster, first_load=False))
                        already.add(rel)

        # 3. Contract validation of every downloaded data file
        #    (manifests after the layer files, episodes.json last: they check that what they list exists)
        registry = validate.load_registry()
        data_dir = root / "data"
        data_files = [f for f in report.files if f.path.startswith("data/") and not f.errors]
        data_files.sort(key=lambda f: (f.path == episodes_path, f.path.endswith("manifest.json")))
        for f in data_files:
            path = root / f.path
            in_static = Path(f.path).relative_to("data").parts[0] in validate.SKIPPED_DIRS
            if path.suffix not in validate.DATA_SUFFIXES:
                continue  # e.g. population.png: presence is enough
            if in_static:
                try:  # front-end asset: must at least be valid JSON
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    f.errors.append(f"invalid JSON: {exc}")
                continue
            f.errors += validate.validate_file(path, registry, data_dir)

    # 4. Load check
    if report.first_load_seconds > max_load_s:
        report.errors.append(
            f"first page load took {report.first_load_seconds:.2f}s (budget {max_load_s:.1f}s)")
    return report


def format_report(report: Report) -> str:
    lines = [f"End-to-end check: {report.url}", ""]
    for f in report.files:
        mark = "ok  " if not f.errors else "FAIL"
        tag = "first-load" if f.first_load else "          "
        lines.append(f"{mark} {tag} {f.path:<40} {f.status or '---'}  {f.size / 1024:8.1f} KB  {f.seconds:6.2f}s")
        lines += [f"     - {e}" for e in f.errors[:10]]
        if len(f.errors) > 10:
            lines.append(f"     … and {len(f.errors) - 10} more")
    lines += ["", f"First page load: {report.first_load_bytes / 1024:.1f} KB in {report.first_load_seconds:.2f}s "
                  f"(budget {report.max_load_s:.1f}s)"]
    lines += [f"FAIL {e}" for e in report.errors]
    lines += [f"note {n}" for n in report.notes]
    lines.append("RESULT: " + ("PASS" if report.ok else "FAIL"))
    return "\n".join(lines)


def markdown_summary(report: Report) -> str:
    rows = ["| | File | HTTP | Size | Time |", "|---|---|---|---|---|"]
    for f in report.files:
        mark = "✅" if not f.errors else "❌ " + "; ".join(f.errors[:2]).replace("|", "\\|")
        rows.append(f"| {mark} | `{f.path}`{' (first load)' if f.first_load else ''} | {f.status or '—'} "
                    f"| {f.size / 1024:.1f} KB | {f.seconds:.2f}s |")
    head = f"### End-to-end check {'✅ PASS' if report.ok else '❌ FAIL'}\n\n{report.url}\n\n"
    tail = (f"\n\n**First page load:** {report.first_load_bytes / 1024:.1f} KB in "
            f"{report.first_load_seconds:.2f}s (budget {report.max_load_s:.1f}s)\n")
    tail += "".join(f"\n- ❌ {e}" for e in report.errors)
    tail += "".join(f"\n- ℹ️ {n}" for n in report.notes)
    return head + "\n".join(rows) + tail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL, help=f"published site (default {DEFAULT_URL})")
    parser.add_argument("--max-load", type=float, default=DEFAULT_MAX_LOAD_S,
                        help="budget in seconds for the first page load (default %(default)s)")
    args = parser.parse_args(argv)

    report = check_site(args.url, args.max_load)
    print(format_report(report))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(markdown_summary(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
