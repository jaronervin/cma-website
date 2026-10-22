"""One-time export of the public WordPress content into content/ as HTML files
with a small front-matter header. Stdlib only.

    python tools/export_wp.py            # pages, posts, events
    python tools/export_wp.py --media    # also download referenced uploads
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SITE = "https://coolfontmountainside.com"
ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
UPLOADS = ROOT / "site-src" / "uploads"
UA = {"User-Agent": "CMA-static-migration/1.0"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r), r.headers


def fetch_all(endpoint, params=""):
    items, page = [], 1
    while True:
        data, headers = get_json(f"{SITE}/wp-json/{endpoint}?per_page=100&page={page}{params}")
        items.extend(data)
        if page >= int(headers.get("X-WP-TotalPages", 1)):
            return items
        page += 1


def rel_path(link):
    """https://coolfontmountainside.com/a/b/ -> a/b"""
    return re.sub(r"^https?://(www\.)?coolfontmountainside\.com/?", "", link).strip("/")


def clean(body):
    # Point uploads at the local copy and internal links at relative-to-root paths.
    body = re.sub(r"https?://(www\.)?coolfontmountainside\.com/wp-content/uploads/", "/uploads/", body)
    body = re.sub(r"https?://(www\.)?coolfontmountainside\.com/", "/", body)
    body = body.replace('"/wp-content/uploads/', '"/uploads/')
    # Download Manager links stay on the live site until the files are moved.
    body = re.sub(r'href=(["\'])/download/', rf"href=\1{SITE}/download/", body)
    # Drop WordPress-generated srcset/sizes; we only keep the referenced file.
    body = re.sub(r'\s(srcset|sizes)="[^"]*"', "", body)
    # Inline plugin <style> blocks.
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    # Download Manager tables -> simple document lists.
    body = re.sub(r'<div class="w3eden">.*?</table>.*?</div>\s*</div>\s*</div>', doc_list, body, flags=re.S)
    # Quick-and-Easy FAQ toggles -> native <details>.
    body = re.sub(
        r'<div id="qaef-\d+" class="qe-faq-toggle[^"]*">\s*<div class="qe-toggle-title">\s*<h4>\s*<i[^>]*></i>\s*(.*?)</h4>\s*</div>\s*<div class="qe-toggle-content">(.*?)</div>\s*</div>',
        lambda m: f"<details><summary>{m.group(1).strip()}</summary>{m.group(2).strip()}</details>",
        body, flags=re.S)
    body = re.sub(r'<h3 class="qe-faqs-group-title">', "<h3>", body)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    # WordPress post-embed iframes; the <blockquote> link beside them is kept.
    body = re.sub(r'<iframe[^>]*class="wp-embedded-content".*?</iframe>', "", body, flags=re.S)
    # Events Calendar blocks: the schedule line (we render dates ourselves),
    # then everything from the price/venue/"add to calendar" widgets on.
    body = re.sub(r'<div\s+class="tribe-events-schedule.*?</div>', "", body, flags=re.S)
    body = re.sub(r'<div\s+class="tribe-block.*', "", body, flags=re.S)
    body = re.sub(r'<p class="wp-block-paragraph"></p>', "", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def doc_list(m):
    items = re.findall(
        r"<a class=\"package-title\" href='(?:" + re.escape(SITE) + r")?(/download/[^']+)'>(.*?)</a>.*?__dt_package_size small-txt'>([^<]*)<",
        m.group(0), flags=re.S)
    # Until the files are moved, document links point at the live WordPress site.
    lis = "\n".join(
        f'  <li><a href="{SITE}{href}">{title}</a> <span class="doc-size">{size}</span></li>'
        for href, title, size in items)
    return f'<ul class="doc-list">\n{lis}\n</ul>'


def write(path, meta, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{header}\n---\n{body}\n", encoding="utf-8")


def main():
    for d in ("pages", "posts", "events"):
        (CONTENT / d).mkdir(parents=True, exist_ok=True)

    pages = fetch_all("wp/v2/pages")
    protected = []
    for p in pages:
        slug_path = rel_path(p["link"]) or "index"
        if p["content"].get("protected"):
            protected.append(slug_path)
            body = '<p class="notice">This page is for members only.</p>'
        else:
            body = clean(p["content"]["rendered"])
        write(CONTENT / "pages" / f"{slug_path}.html",
              {"title": html.unescape(p["title"]["rendered"]).replace("Protected: ", ""),
               "protected": str(bool(p["content"].get("protected"))).lower(),
               "menu_order": p.get("menu_order", 0)},
              body)

    cats = {c["id"]: c["name"] for c in fetch_all("wp/v2/categories")}
    posts = fetch_all("wp/v2/posts", "&_embed=wp:featuredmedia")
    for p in posts:
        media = (p.get("_embedded") or {}).get("wp:featuredmedia") or [{}]
        image = clean(media[0].get("source_url", "")) if media[0] else ""
        write(CONTENT / "posts" / f"{p['date'][:10]}-{p['slug']}.html",
              {"title": html.unescape(p["title"]["rendered"]),
               "path": rel_path(p["link"]),
               "date": p["date"],
               "categories": ", ".join(html.unescape(cats.get(c, "")) for c in p["categories"]),
               "image": image},
              clean(p["content"]["rendered"]))

    events, url = [], f"{SITE}/wp-json/tribe/events/v1/events?per_page=50&start_date=2020-01-01"
    while url:
        data, _ = get_json(url)
        events.extend(data.get("events", []))
        url = data.get("next_rest_url")
    for e in events:
        write(CONTENT / "events" / f"{e['start_date'][:10]}-{e['slug']}.html",
              {"title": html.unescape(e["title"]),
               "path": rel_path(e["url"]),
               "start": e["start_date"], "end": e["end_date"],
               "all_day": str(e.get("all_day", False)).lower(),
               "venue": html.unescape((e.get("venue") or {}).get("venue", "") if isinstance(e.get("venue"), dict) else "")},
              clean(e.get("description", "")))

    print(f"pages={len(pages)} posts={len(posts)} events={len(events)}")
    print("password-protected (not exported):", ", ".join(protected) or "none")

    if "--media" in sys.argv:
        download_media()


def download_media():
    # File paths only: stop at the extension, ignoring ?query, #anchor or /suffix.
    pattern = re.compile(r'/uploads/([^"\'\s)?#]+?\.[A-Za-z0-9]{2,5})(?=["\'\s)?#/]|$)')
    refs = set()
    for f in [*CONTENT.rglob("*.html"), *(ROOT / "site-src").rglob("*.json")]:
        refs.update(pattern.findall(f.read_text(encoding="utf-8")))
    ok = fail = 0
    for r in sorted(refs):
        dest = UPLOADS / r
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(f"{SITE}/wp-content/uploads/{r}", headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            ok += 1
        except Exception as ex:  # keep going; report at the end
            print("  failed:", r, ex)
            fail += 1
    print(f"media downloaded={ok} failed={fail}")


if __name__ == "__main__":
    main()
