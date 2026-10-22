# Coolfont Mountainside Association website (static prototype)

Static rebuild of coolfontmountainside.com. No WordPress, no database, no npm, just Python 3 (standard library only).

## Layout

| Path | What it is |
|---|---|
| `content/pages/` | One HTML file per page. The folder path is the URL (`content/pages/homeowners/assessments.html` → `/homeowners/assessments/`). |
| `content/posts/` | News posts, `YYYY-MM-DD-slug.html`. The `path:` line in the header is the URL. |
| `content/events/` | Calendar events. |
| `site-src/site.json` | Menus, sidebar contacts, quick links, carousel photos, redirects. |
| `site-src/assets/` | `site.css`, `site.js`, favicon. |
| `site-src/uploads/` | Images and PDFs (same paths as the old `/wp-content/uploads/`). |
| `tools/build.py` | Builds everything into `_site/`. |
| `tools/export_wp.py` | One-time export from the live WordPress site. |

Each content file starts with a small header:

```
---
title: Board of Directors Meeting – 11/9/26
path: 2026/10/14/board-of-directors-meeting-11-9-26
date: 2026-10-14T09:00:00
categories: Board of Directors
image:
---
<p>Body HTML…</p>
```

## Common tasks

- **Post news:** copy any file in `content/posts/`, change the header and body, commit.
- **Add an event:** copy a file in `content/events/`. Events dated today or later show under "Upcoming".
- **Change the menu or sidebar contacts:** edit `site-src/site.json`.
- **Add a PDF:** put it under `site-src/uploads/YYYY/MM/` and link to `/uploads/YYYY/MM/name.pdf`.

## Build and preview locally

```bash
python tools/build.py
```

```bash
python -m http.server 8417 --directory _site
```

Then open http://localhost:8417.

Pushing to `main` deploys through `.github/workflows/deploy.yml`, which also rebuilds daily so the upcoming-events list stays current.
