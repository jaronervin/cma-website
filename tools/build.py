"""Build the static site from content/ + site-src/ into _site/. Stdlib only.

    python tools/build.py
    BASE_PATH=/cma-site python tools/build.py   # when served from a subfolder
"""
import hashlib
import html
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
SRC = ROOT / "site-src"
OUT = ROOT / "_site"
SITE = json.loads((SRC / "site.json").read_text(encoding="utf-8"))
TODAY = date.today().isoformat()
# "" at a domain root; "/repo-name" for a GitHub Pages project site.
BASE = os.environ.get("BASE_PATH", "").rstrip("/")
# Cache-busting tag for site.css / site.js, so browsers pick up changes right away.
ASSET_VER = hashlib.sha1(b"".join((SRC / "assets" / n).read_bytes() for n in ("site.css", "site.js"))).hexdigest()[:8]


# ---------- content loading ----------

def load(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(": ")
        meta[k.strip(":")] = v.strip()
    meta["body"] = m.group(2).strip()
    return meta


def collection(name):
    return [load(p) for p in sorted((CONTENT / name).rglob("*.html"))]


def excerpt(body, words=40):
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    parts = text.split()
    return " ".join(parts[:words]) + (" …" if len(parts) > words else "")


def nice_date(iso):
    d = datetime.fromisoformat(iso[:19].replace(" ", "T"))
    return f"{d:%B} {d.day}, {d.year}"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------- layout ----------

def nav_html(current):
    items = []
    for item in SITE["nav"]:
        active = " aria-current=\"page\"" if item["href"] == current else ""
        kids = item.get("children")
        if kids:
            sub = "".join(f'<li><a href="{c["href"]}">{html.escape(c["title"])}</a></li>' for c in kids)
            items.append(
                f'<li class="has-sub"><a href="{item["href"]}"{active}>{html.escape(item["title"])}</a>'
                f'<button class="sub-toggle" aria-label="Show {html.escape(item["title"])} pages" aria-expanded="false"></button>'
                f'<ul class="sub">{sub}</ul></li>')
        else:
            items.append(f'<li><a href="{item["href"]}"{active}>{html.escape(item["title"])}</a></li>')
    return "".join(items)


def sidebar_html():
    links = "".join(f'<li><a href="{q["href"]}">{html.escape(q["title"])}</a></li>' for q in SITE["quick_links"])
    return f"""
<aside class="sidebar">
  <a class="btn btn-cta" href="{SITE['pool_passes_url']}">Buy Pool Passes</a>
  <form class="search" action="/search/" role="search">
    <label class="visually-hidden" for="side-q">Search</label>
    <input id="side-q" name="q" type="search" placeholder="Search the site">
    <button type="submit">Search</button>
  </form>
  <section><h2>Handy Contacts</h2>{SITE['contacts_html']}</section>
  <section><h2>Quick Links</h2><ul class="plain">{links}</ul></section>
  <img class="side-logo" src="{SITE['logo']}" alt="Coolfont Mountainside Association logo">
</aside>"""


def page(title, main, current="", hero="", sidebar=True, description=""):
    full_title = SITE["title"] if title == SITE["title"] else f"{title} | {SITE['title']}"
    social = " · ".join(f'<a href="{s["href"]}">{s["title"]}</a>' for s in SITE["social"])
    layout = f'<div class="layout">{main}{sidebar_html()}</div>' if sidebar else main
    desc = html.escape(description or excerpt(main, 30))
    return f"""<!doctype html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="/assets/site.css?v={ASSET_VER}">
<link rel="icon" href="/assets/favicon.png">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-row">
    <a class="site-title" href="/">{html.escape(SITE['title'])}</a>
    <button class="menu-toggle" aria-expanded="false" aria-controls="site-nav">Menu</button>
  </div>
  <nav id="site-nav" class="site-nav" aria-label="Main"><ul class="wrap">{nav_html(current)}</ul></nav>
</header>
{hero}
<main id="main" class="wrap">
{layout}
</main>
<footer class="site-footer">
  <div class="wrap footer-row">
    <p>{SITE['footer_address']}</p>
    <p>{social}</p>
  </div>
  <p class="copyright">Copyright © {date.today().year} Coolfont Mountainside Association. All rights reserved.</p>
</footer>
<script src="/assets/site.js?v={ASSET_VER}" defer></script>
</body>
</html>
"""


def with_base(text):
    """Prefix root-relative links (href="/x", src="/x", url=/x) with BASE."""
    if not BASE:
        return text
    text = re.sub(r'((?:href|src|action)=")/(?!/)', lambda m: f"{m.group(1)}{BASE}/", text)
    return re.sub(r"(url=)/(?!/)", lambda m: f"{m.group(1)}{BASE}/", text)


def write(rel, text):
    dest = OUT / rel.strip("/") / "index.html" if not rel.endswith(".html") else OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(with_base(text), encoding="utf-8")


def carousel():
    slides = "".join(
        f'<img src="{src}" alt="" {"" if i == 0 else "loading=lazy "}class="slide{" is-active" if i == 0 else ""}">'
        for i, src in enumerate(SITE["carousel"]))
    return f"""<div class="hero" aria-label="Photos of Coolfont">
  {slides}
  <button class="hero-prev" aria-label="Previous photo">‹</button>
  <button class="hero-next" aria-label="Next photo">›</button>
</div>"""


# ---------- renderers ----------

def post_card(p):
    cats = "".join(
        f'<a class="tag" href="/category/{slugify(c)}/">{html.escape(c)}</a>'
        for c in p["categories"].split(", ") if c)
    return f"""<article class="card">
  <div class="card-meta"><time datetime="{p['date']}">{nice_date(p['date'])}</time>{cats}</div>
  <h2><a href="/{p['path']}/">{html.escape(p['title'])}</a></h2>
  <p>{html.escape(excerpt(p['body']))}</p>
</article>"""


def pager(base, n, total):
    if total <= 1:
        return ""
    url = lambda i: base if i == 1 else f"{base}page/{i}/"
    prev = f'<a href="{url(n - 1)}">‹ Newer</a>' if n > 1 else "<span></span>"
    nxt = f'<a href="{url(n + 1)}">Older ›</a>' if n < total else "<span></span>"
    return f'<nav class="pager" aria-label="Pages">{prev}<span>Page {n} of {total}</span>{nxt}</nav>'


def build_listing(posts, base, heading, hero="", current=""):
    per = SITE["posts_per_page"]
    total = max(1, -(-len(posts) // per))
    for n in range(1, total + 1):
        chunk = posts[(n - 1) * per: n * per]
        h1 = f'<h1 class="visually-hidden">{heading}</h1>' if base == "/" else f"<h1>{heading}</h1>"
        main = f'<div class="content">{h1}{"".join(post_card(p) for p in chunk)}{pager(base, n, total)}</div>'
        title = SITE["title"] if base == "/" else heading
        write(base if n == 1 else f"{base}page/{n}/", page(title, main, current, hero if n == 1 else ""))


def owner_docs_html():
    """Members-only documents live in a Google Drive folder shared with members;
    Google enforces access, so nothing private is ever published with the site."""
    od = SITE["owner_docs"]
    if od.get("members_url"):
        # Email sign-in gatekeeper (members/): owners need only their email address.
        return f"""
<p>Board minutes, budgets, committee reports and other Association records are available to CMA members.</p>
<p>To view them, sign in with the email address the Association has on file for you. We'll email you a link,
so there's no password to remember. Once you're signed in, this computer remembers you for six months.</p>
<p><a class="btn btn-primary" href="{od['members_url']}">Sign in to Owner Documents</a></p>
<p class="kicker">Need help, or not sure which email is on file? Contact {od['contact']}.</p>
"""
    folder = f"https://drive.google.com/drive/folders/{od['folder_id']}"
    embed = f"https://drive.google.com/embeddedfolderview?id={od['folder_id']}#list"
    return f"""
<p>Board minutes, budgets, committee reports and other Association records are available to CMA members.
They're kept in a private Google Drive folder. {od['access_note']}, so you'll need to be signed in to Google
with the email address the Association has on file.</p>
<p><a class="btn btn-primary" href="{folder}" target="_blank" rel="noopener">Open Owner Documents in Google Drive</a></p>
<details class="help">
  <summary>Can't open the folder?</summary>
  <ul>
    <li><strong>"You need access":</strong> you're signed in to Google with a different email than the one on file.
      Switch accounts (click your picture in the top-right corner of Google Drive), or click <em>Request access</em>.</li>
    <li><strong>No Google account?</strong> You can create one with your existing email address, no Gmail needed:
      go to <a href="https://accounts.google.com/signup" target="_blank" rel="noopener">accounts.google.com/signup</a>
      and choose <em>Use your existing email</em>.</li>
    <li><strong>Not on the member list yet?</strong> Contact {od['contact']}.</li>
  </ul>
</details>
<h2>Browse here</h2>
<p class="kicker">If you're signed in and have access, the folder appears below. Some browsers (Safari, Firefox) block this
view; if it's blank, use the button above.</p>
<iframe class="drive-embed" src="{embed}" title="Owner Documents folder" loading="lazy"></iframe>
"""


def event_when(e):
    if e["all_day"] == "true":
        return nice_date(e["start"])
    start = datetime.fromisoformat(e["start"].replace(" ", "T"))
    return f"{nice_date(e['start'])}, {start.strftime('%I:%M %p').lstrip('0')}"


def build_events(events):
    upcoming = sorted((e for e in events if e["start"][:10] >= TODAY), key=lambda e: e["start"])
    past = sorted((e for e in events if e["start"][:10] < TODAY), key=lambda e: e["start"], reverse=True)

    def rows(es):
        return "".join(
            f'<li><a href="/{e["path"]}/">{html.escape(e["title"])}</a><span class="when">{event_when(e)}</span></li>'
            for e in es)

    main = f"""<div class="content">
<h1>Calendar</h1>
<h2>Upcoming events</h2>
<ul class="event-list">{rows(upcoming) or '<li>No upcoming events.</li>'}</ul>
<details class="past"><summary>Past events ({len(past)})</summary><ul class="event-list">{rows(past)}</ul></details>
</div>"""
    write("/events/", page("Calendar", main, "/events/"))
    for e in events:
        venue = f"<p><strong>Where:</strong> {html.escape(e['venue'])}</p>" if e["venue"] else ""
        body = f"""<article class="content">
<p class="kicker"><a href="/events/">Calendar</a></p>
<h1>{html.escape(e['title'])}</h1>
<p class="event-when"><strong>When:</strong> {event_when(e)}</p>{venue}
{e['body']}
</article>"""
        write(f"/{e['path']}/", page(e["title"], body, "/events/"))


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")
    if (SRC / "uploads").exists():
        shutil.copytree(SRC / "uploads", OUT / "uploads")

    pages = [p for p in (load(f) | {"_path": f.relative_to(CONTENT / "pages").with_suffix("").as_posix()}
                         for f in sorted((CONTENT / "pages").rglob("*.html")))
             if p["_path"] not in SITE["skip_pages"]]
    posts = sorted(collection("posts"), key=lambda p: p["date"], reverse=True)
    events = collection("events")

    search_index = []

    for p in pages:
        path = "/" + p["_path"] + "/"
        section = "/" + p["_path"].split("/")[0] + "/"
        body = p["body"]
        if p["_path"] == "homeowners/owner-documents":
            body = owner_docs_html()
        elif p["protected"] == "true":
            body = ('<div class="notice"><p><strong>Members only.</strong> This page will sit behind '
                    'the owners\' sign-in once the secure area is set up (see the migration plan).</p></div>')
        main = f'<article class="content"><h1>{html.escape(p["title"])}</h1>{body}</article>'
        write(path, page(p["title"], main, section))
        if p["protected"] != "true":
            search_index.append({"t": p["title"], "u": path, "x": excerpt(p["body"], 60)})

    for p in posts:
        cats = ", ".join(f'<a href="/category/{slugify(c)}/">{html.escape(c)}</a>'
                         for c in p["categories"].split(", ") if c)
        main = f"""<article class="content">
<p class="kicker"><time datetime="{p['date']}">{nice_date(p['date'])}</time>{' · ' + cats if cats else ''}</p>
<h1>{html.escape(p['title'])}</h1>
{p['body']}
</article>"""
        write(f"/{p['path']}/", page(p["title"], main))
        search_index.append({"t": p["title"], "u": f"/{p['path']}/", "d": p["date"][:10], "x": excerpt(p["body"], 60)})

    build_listing(posts, "/", "Latest news", hero=carousel(), current="/")

    by_cat = {}
    for p in posts:
        for c in filter(None, p["categories"].split(", ")):
            by_cat.setdefault(c, []).append(p)
    for c, ps in by_cat.items():
        build_listing(ps, f"/category/{slugify(c)}/", c)

    build_events(events)

    for old, new in SITE["redirects"].items():
        write(f"/{old}/", f'<!doctype html><meta charset="utf-8"><title>Moved</title>'
                          f'<meta http-equiv="refresh" content="0; url={new}"><link rel="canonical" href="{new}">'
                          f'<a href="{new}">This page has moved.</a>')

    search_main = """<div class="content"><h1>Search</h1>
<form class="search big" action="/search/" role="search"><label class="visually-hidden" for="q">Search</label>
<input id="q" name="q" type="search" placeholder="Search news, pages, documents"><button type="submit">Search</button></form>
<ol id="results" class="results"></ol></div>"""
    write("/search/", page("Search", search_main))
    (OUT / "search-index.json").write_text(json.dumps(search_index, ensure_ascii=False), encoding="utf-8")

    write("404.html", page("Page not found", '<div class="content"><h1>Page not found</h1>'
                           '<p>Sorry, that page doesn\'t exist. Try the <a href="/search/">search</a> or the menu above.</p></div>'))

    urls = [f"/{p['_path']}/" for p in pages] + [f"/{p['path']}/" for p in posts] + ["/", "/events/"]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{SITE['url']}{u}</loc></url>" for u in urls) + "\n</urlset>\n",
        encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")

    print(f"built {len(pages)} pages, {len(posts)} posts, {len(events)} events, "
          f"{len(by_cat)} categories -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
