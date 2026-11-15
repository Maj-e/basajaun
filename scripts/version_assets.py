"""Stamp the deployed front end with a version, so a deploy never mixes old and new files.

GitHub Pages lets browsers cache every file for 10 minutes. The page is made of ES modules:
a visitor could get some modules from the previous deploy and others from the new one, and a
mix stops the page before anything is drawn. Adding `?v=<version>` to every module import and
to the scripts and stylesheets of index.html gives each deploy its own URLs.

Run by .github/workflows/deploy.yml on the copy that is published (never on the repository):
    python scripts/version_assets.py web <version>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# `from "./x.js"`, `import "./x.js"`, `import("./x.js")`: relative specifiers only
IMPORT = re.compile(r"""((?:\bfrom|\bimport)\s*\(?\s*["'])(\.{1,2}/[^"'?]+\.js)(["'])""")
# src="app.js" / href="style.css" in index.html: local .js and .css only (no http, no data/)
ASSET = re.compile(r"""((?:src|href)=")(?!https?:|//|data/)([^"?#]+\.(?:js|css))(")""")


def stamp_js(text: str, version: str) -> str:
    return IMPORT.sub(lambda m: f"{m[1]}{m[2]}?v={version}{m[3]}", text)


def stamp_html(text: str, version: str) -> str:
    return ASSET.sub(lambda m: f"{m[1]}{m[2]}?v={version}{m[3]}", text)


def main() -> None:
    root, version = Path(sys.argv[1]), sys.argv[2]
    for path in root.rglob("*.js"):
        if "vendor" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        stamped = stamp_js(text, version)
        if stamped != text:
            path.write_text(stamped, encoding="utf-8")
    index = root / "index.html"
    index.write_text(stamp_html(index.read_text(encoding="utf-8"), version), encoding="utf-8")
    print(f"Stamped {root} with v={version}")


if __name__ == "__main__":
    main()
