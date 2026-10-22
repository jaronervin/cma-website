"""Download the Download Manager documents linked from public pages into
site-src/uploads/docs/ and rewrite content/ links to point at the local copies.
Stdlib only. Safe to re-run: existing files are skipped.

    python tools/fetch_docs.py
"""
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import unquote

SITE = "https://coolfontmountainside.com"
ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DOCS = ROOT / "site-src" / "uploads" / "docs"
MANIFEST = DOCS / "manifest.json"
UA = {"User-Agent": "CMA-static-migration/1.0"}
LINK = re.compile(re.escape(SITE) + r"/download/([a-z0-9-]+)/?")


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=180)


def filename_for(slug, resp):
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    ext = Path(unquote(m.group(1))).suffix.lower() if m else ""
    if not ext:
        ext = {"application/pdf": ".pdf", "audio/mp4": ".m4a"}.get(resp.headers.get_content_type(), ".bin")
    return f"{slug}{ext}"


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    slugs = sorted({s for f in CONTENT.rglob("*.html") for s in LINK.findall(f.read_text(encoding="utf-8"))})
    print(f"{len(slugs)} linked documents, {len(manifest)} already downloaded")

    for slug in slugs:
        if slug in manifest and (DOCS / manifest[slug]).exists():
            continue
        try:
            page = fetch(f"{SITE}/download/{slug}/").read().decode("utf-8", "replace")
            m = re.search(r"wpdmdl=(\d+)", page)
            if not m:
                print("  no download id:", slug)
                continue
            with fetch(f"{SITE}/download/{slug}/?wpdmdl={m.group(1)}") as resp:
                name = filename_for(slug, resp)
                (DOCS / name).write_bytes(resp.read())
            manifest[slug] = name
            MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True))
            print("  ok", name)
        except Exception as ex:  # keep going; report at the end
            print("  failed:", slug, ex)

    # Point content at the local copies.
    changed = 0
    for f in CONTENT.rglob("*.html"):
        text = f.read_text(encoding="utf-8")
        new = LINK.sub(lambda m: f"/uploads/docs/{manifest[m.group(1)]}" if m.group(1) in manifest else m.group(0), text)
        if new != text:
            f.write_text(new, encoding="utf-8")
            changed += 1
    missing = [s for s in slugs if s not in manifest]
    print(f"downloaded {len(manifest)} documents; updated links in {changed} files; missing: {missing or 'none'}")


if __name__ == "__main__":
    main()
