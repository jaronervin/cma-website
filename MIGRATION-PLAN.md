# CMA website migration plan: WP Engine WordPress → free static hosting

*Draft, October 22, 2026*

## Summary

The site at coolfontmountainside.com is hosted on **WP Engine**, a paid managed WordPress host. Almost everything on it is read-only content: pages, news posts, an events list and downloadable PDFs. That content can be served as a static site at no cost. A working prototype of the public site has already been generated from the live content (see the README).

The only parts that need more than static hosting are the two password-protected pages (**Owner Documents** and **Member Directory**). Those get their own phase below.

## What's on the current site

| Item | Count / detail | Static replacement |
|---|---|---|
| Pages | 35 (29 public, 2 password-protected, 6 leftover membership-plugin pages) | HTML files in `content/pages/`, same URLs |
| News posts | 161 (2018–2026), 5 categories | `content/posts/`, same URLs; paged news feed and category pages |
| Events (The Events Calendar plugin) | 142 (8 upcoming) | `content/events/` with an Upcoming/Past list. Optionally switch to an embedded Google Calendar the board edits directly |
| Documents (Download Manager plugin) | ~290 PDFs: governing docs, newsletters, plat maps, committee reports | Plain PDF links under `/uploads/`, shown as simple document lists |
| Images and other uploads | 52 referenced files (~48 MB, mostly PDFs; one 7 MB photo resized to 206 KB) | Copied under `/uploads/`, same paths |
| Member Directory (Connections plugin) | Password-protected | Phase 2 |
| Owner Documents | Password-protected | Phase 2 |
| Search | WordPress search | Built-in client-side search (no service needed) |
| Analytics (MonsterInsights) | Google Analytics | Add the GA tag to the template, or use Cloudflare Web Analytics (free, no cookies) |
| Already off-site | Assessment payments (invoice link), pool passes (Eventbrite), Google Group, Facebook, Zoom | No change |

**Leftovers worth knowing about:** `/register/*` pages from Restrict Content Pro (a paid membership plugin) are still on the site. If the HOA still pays for a Restrict Content Pro license, that cost goes away too.

## Hosting recommendation

**GitHub Pages**, the same setup as the board member's other sites, deployed by GitHub Actions (`.github/workflows/deploy.yml`).

- Cost: $0. The repo is about 60 MB with photos (more once all PDFs are moved in), well within GitHub's limits.
- The HOA should own the GitHub **organization** (e.g. `CoolfontMountainside`), with at least two board members as owners, so the site doesn't depend on one person's account.
- The domain stays wherever it's registered. Only DNS records change.

**Alternative: Cloudflare Pages** (also free). If the board picks Cloudflare Access for the secure area in Phase 2, hosting the whole site on Cloudflare keeps everything in one place. The build is identical either way.

## Phase 1: public site (prototype done)

1. ✅ Export all public content from WordPress (`tools/export_wp.py`).
2. ✅ Strip plugin markup: document tables become simple lists, FAQ accordions become native expand/collapse, calendar widgets removed.
3. ✅ Rebuild layout: same menus, carousel, sidebar contacts, quick links and footer. Works on phones.
4. ✅ Keep every existing URL so old links, bookmarks and Google results still work. Add redirects for short links WordPress used to resolve on its own (`/committees`, `/calendar`, `/design-guidelines`, …).
5. ✅ **Move the publicly linked Download Manager documents** into `/uploads/docs/` (`tools/fetch_docs.py`). Links now point to the local copies.
6. ✅ **Resize photos.** Only one was oversized (7 MB → 206 KB). The original is kept locally in `archive/original-photos/`, outside Git.
7. ☐ **Fix links that are already broken on the live site** (old pool-rules PDFs from 2020–2022 and 2025, the 2018 annual-dinner PDF, a malformed link on the Task Forces page, two links to deleted events).
8. ☐ Board review of the prototype. Content and wording are unchanged, so this is mostly look and feel.

## Phase 2: Owner Documents and Member Directory

The current site protects both pages with **one shared page password**, which owners lose and can't recover on their own. A security review of how the current site protects these documents was done separately and shared with the Board.

**Requirement:** documents available to the whole membership but not the public, usable by owners who aren't comfortable with technology (no new accounts, nothing to remember), and easy for the Board to maintain. Owner-only documents never go into this GitHub repo.

Options considered:

| Option | Cost | Owner experience | Verdict |
|---|---|---|---|
| Google Drive shared with a Google Group | Free | Must have or create a Google account | Too much friction for many owners |
| Cloudflare Access | ~$7/user/mo beyond 50 users | Email + one-time code | Too expensive at ~200 owners |
| Shared password page | Free | One password for everyone | Same problems as today |
| HOA portal software | Monthly fee | Account with another company | Same friction, plus cost |
| **Email sign-in gatekeeper + Google Drive** | **Free** | **Enter your email, click the link** | **Chosen** |

**Built (Oct 22, 2026):** a small Cloudflare Worker (`members/`) in front of a private Google Drive folder. Owners enter their email; if it's on the member list (a Google Sheet), they get a sign-in link and a 6-digit code, and stay signed in for 180 days. The Board adds documents by dropping them into the Drive folder and manages access by editing the Sheet. Setup and maintenance: `SETUP-MEMBERS-AREA.md`.

**To go live:**
1. Verify `coolfontmountainside.com` in Resend (a few DNS records) so sign-in emails reach every owner.
2. Move the Drive folder and member Sheet to a Board-owned Google account; update their IDs in `members/wrangler.toml`.
3. Fill the member Sheet from the assessment roster; upload the full document set to the Drive folder.

## Phase 3 (separate decision): individual homeowner logins

Letting ~200 owners sign in to update their contact info or see lot-specific records needs a real backend: user accounts, a database, password resets and access rules. Options:

- **Hosted backend on a free tier** (Supabase or Firebase) with a small owners portal. Free at this size, but it's custom software holding personal data that someone has to maintain after the current board.
- **Purpose-built HOA portal** (e.g. PayHOA, AppFolio, TownSq): paid, but supported, and usually also handles dues and announcements.
- **Google Form + Sheet** for contact updates, reviewed by the secretary: free and low-risk, but no self-service view.

This doesn't block Phases 1 and 2.

## Cutover checklist

1. Create the GitHub organization and repo; push this project; enable Pages (Settings → Pages → Source: GitHub Actions).
2. Add a `CNAME` file containing `coolfontmountainside.com`, then add the custom domain in Pages settings.
3. Lower the DNS TTL a day ahead. Then point the apex `A` records to GitHub Pages (185.199.108.153, .109.153, .110.153, .111.153) and `www` `CNAME` to `<org>.github.io`. Turn on "Enforce HTTPS" once the certificate is issued.
4. Check that the domain's **email (MX) records are untouched.** Confirm whether any `@coolfontmountainside.com` email runs through WP Engine. None was seen, but verify.
5. Spot-check: home, Association Documents, a 2019 post, a PDF link, search, phone view.
6. **Before cancelling WP Engine:** take a full backup (WP Engine backup + `wp-content/uploads` zip), export the Member Directory (Connections → export CSV), and keep both in the HOA's Google Drive.
7. Cancel WP Engine (and any Restrict Content Pro / Download Manager Pro licenses) after a 2–4 week overlap.

## Who maintains it, and how

Board members aren't expected to know Git. Options:

- **Edit on GitHub.com:** open a file, click the pencil, save. Fine for occasional edits by one or two people.
- **Add a simple visual editor:** Pages CMS or Decap CMS gives a WordPress-like form for news posts and events, saving to GitHub behind the scenes. Free. Recommended if more than one or two people post news.
- **Calendar via Google Calendar:** have the board edit a shared Google Calendar and embed it, so nobody touches files for events.

## Estimated effort

| Work | Estimate |
|---|---|
| Phase 1 remaining (PDF move, image resize, broken links, review fixes) | 1–2 sessions |
| Cutover (DNS, verification) | 1 hour + DNS wait |
| Phase 2, option A | 1 session (mostly sharing setup and updating links) |
| Visual editor setup (optional) | 1 session |
