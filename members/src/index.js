// CMA members gatekeeper: email sign-in in front of a private Google Drive folder.
//
// Owners enter their email; if it's on the member list (a Google Sheet), they get a
// sign-in link and a 6-digit code by email. Signing in sets a cookie, and the Worker
// then lists and serves files from the Drive folder using a Google service account.
// Nothing is stored server-side: links, codes and cookies are HMAC-signed with
// SESSION_SECRET. No dependencies. Config: wrangler.toml [vars]; secrets come from
// GitHub Actions (see .github/workflows/members.yml).

const LINK_MINUTES = 30;
const CODE_WINDOW_SECONDS = 600; // codes stay valid for 10-20 minutes
const CACHE_MS = 5 * 60 * 1000; // member list and folder listing refresh every 5 minutes
const COOKIE = "cma_session";
const FOLDER = "application/vnd.google-apps.folder";
const enc = new TextEncoder();

export default {
  async fetch(request, env, ctx) {
    let response;
    try {
      response = await route(request, env, ctx);
    } catch (err) {
      console.error(err && err.stack ? err.stack : err);
      response = page(env, "Temporarily unavailable",
        "<p>Sorry, the member documents are temporarily unavailable. Please try again in a few minutes.</p>", 500);
    }
    return withSecurityHeaders(response, env);
  },
};

async function route(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname;
  if (request.method === "POST" && path === "/login") return login(request, env, ctx, url);
  if (request.method === "POST" && path === "/code") return checkCode(request, env);
  if (request.method === "POST" && path === "/logout") return redirect("/", sessionCookie("", 0));
  if (path === "/verify") return verifyLink(url, env);

  const email = await currentMember(request, env);
  if (!email) return path === "/" ? signInPage(env) : redirect("/");
  if (path === "/") return documentsPage(env, email);
  const m = path.match(/^\/file\/([A-Za-z0-9_-]+)$/);
  if (m) return serveFile(env, m[1]);
  return page(env, "Not found", '<p>That page doesn\'t exist. <a href="/">Back to Owner Documents</a></p>', 404);
}

// ---------- sign-in flow ----------

async function login(request, env, ctx, url) {
  const form = await request.formData();
  const email = normalizeEmail(form.get("email"));
  if (!email) return signInPage(env, "Please enter a valid email address.");
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await allowed(env.LOGIN_LIMIT, "ip:" + ip)) || !(await allowed(env.EMAIL_LIMIT, "send:" + email))) {
    return signInPage(env, "Too many requests. Please wait a minute and try again.");
  }
  // Send in the background so the response looks the same whether or not the address is on file.
  ctx.waitUntil((async () => {
    if ((await members(env)).has(email)) await sendSignInEmail(env, url.origin, email);
  })().catch((err) => console.error("sign-in email failed:", err && err.stack ? err.stack : err)));
  return checkEmailPage(env, email);
}

async function checkCode(request, env) {
  const form = await request.formData();
  const email = normalizeEmail(form.get("email"));
  const code = String(form.get("code") || "").replace(/\D/g, "");
  if (!email) return signInPage(env);
  if (!(await allowed(env.LOGIN_LIMIT, "code:" + email))) {
    return checkEmailPage(env, email, "Too many attempts. Please wait a minute and try again.");
  }
  const slot = Math.floor(Date.now() / 1000 / CODE_WINDOW_SECONDS);
  const valid = code.length === 6 &&
    (code === await codeFor(env, email, slot) || code === await codeFor(env, email, slot - 1));
  if (valid && (await members(env)).has(email)) return startSession(env, email);
  return checkEmailPage(env, email, "That code didn't work. Check the latest email, or request a new one.");
}

async function verifyLink(url, env) {
  const payload = await verifyToken(env, url.searchParams.get("t") || "", "link");
  if (payload && (await members(env)).has(payload.e)) return startSession(env, payload.e);
  return signInPage(env, "That sign-in link has expired or was already replaced. Enter your email to get a new one.");
}

async function startSession(env, email) {
  const days = Number(env.SESSION_DAYS || 180);
  const token = await makeToken(env, "session", email, days * 86400);
  return redirect("/", sessionCookie(token, days * 86400));
}

async function currentMember(request, env) {
  const cookies = request.headers.get("Cookie") || "";
  const m = cookies.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  if (!m) return null;
  const payload = await verifyToken(env, m[1], "session");
  // Re-checking the list means removing someone from the Sheet ends their access within minutes.
  return payload && (await members(env)).has(payload.e) ? payload.e : null;
}

function sessionCookie(value, maxAge) {
  return { "Set-Cookie": `${COOKIE}=${value}; Max-Age=${maxAge}; Path=/; HttpOnly; Secure; SameSite=Lax` };
}

async function sendSignInEmail(env, origin, email) {
  const link = `${origin}/verify?t=${await makeToken(env, "link", email, LINK_MINUTES * 60)}`;
  const code = await codeFor(env, email, Math.floor(Date.now() / 1000 / CODE_WINDOW_SECONDS));
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.MAIL_FROM,
      to: [email],
      subject: "Your CMA Owner Documents sign-in link",
      text: `Click this link to view CMA Owner Documents:\n\n${link}\n\n` +
        `Or enter this code on the sign-in page: ${code}\n\n` +
        `The link and code work for about ${LINK_MINUTES} minutes. If you didn't ask for this, you can ignore this email.\n\n` +
        "Coolfont Mountainside Association",
      html: `<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#23303b">
<p>Click the button below to view <strong>CMA Owner Documents</strong>.</p>
<p><a href="${esc(link)}" style="display:inline-block;background:#2f5d7c;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:bold">View Owner Documents</a></p>
<p>Or enter this code on the sign-in page:</p>
<p style="font-size:28px;font-weight:bold;letter-spacing:6px">${code}</p>
<p style="color:#5f6b76">The link and code work for about ${LINK_MINUTES} minutes. If you didn't ask for this, you can ignore this email.</p>
<p style="color:#5f6b76">Coolfont Mountainside Association</p></div>`,
    }),
  });
  if (!res.ok) throw new Error(`Resend ${res.status}: ${await res.text()}`);
}

// ---------- pages ----------

function signInPage(env, message = "") {
  return page(env, "Owner Documents", `
<h1>Owner Documents</h1>
<p>Board minutes, budgets, committee reports and other Association records are available to CMA members.</p>
<p>Enter the email address the Association has on file for you. We'll email you a link to sign in, with no password to remember.</p>
${message ? `<div class="notice"><p>${esc(message)}</p></div>` : ""}
<form class="search big" method="post" action="/login">
  <label class="visually-hidden" for="email">Email address</label>
  <input id="email" name="email" type="email" autocomplete="email" required placeholder="you@example.com">
  <button type="submit">Email me a link</button>
</form>
<p class="kicker">Not sure which email is on file, or need help? Contact the Communications Committee
(see <a href="${siteUrl(env)}/association/committees/">Committees</a>).</p>`);
}

function checkEmailPage(env, email, message = "") {
  return page(env, "Check your email", `
<h1>Check your email</h1>
${message ? `<div class="notice"><p>${esc(message)}</p></div>` : ""}
<p>If <strong>${esc(email)}</strong> is on the member list, we've sent it a sign-in link. It should arrive within a minute or two.
Check your spam or junk folder if you don't see it.</p>
<p>Click the button in the email, <strong>or</strong> type the 6-digit code from the email here:</p>
<form class="search big" method="post" action="/code">
  <input type="hidden" name="email" value="${esc(email)}">
  <label class="visually-hidden" for="code">6-digit code</label>
  <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]*" maxlength="7" required placeholder="123456">
  <button type="submit">Sign in</button>
</form>
<p class="kicker">No email after a few minutes? <a href="/">Try again</a>, or contact the Communications Committee
(see <a href="${siteUrl(env)}/association/committees/">Committees</a>). They can check which address is on file.</p>`);
}

async function documentsPage(env, email) {
  const { tree } = await driveTree(env);
  const sections = tree.folders.map((f) => renderFolder(f, 2)).join("");
  const loose = tree.files.length ? `<h2>Other documents</h2>${fileList(tree.files)}` : "";
  return page(env, "Owner Documents", `
<h1>Owner Documents</h1>
<form method="post" action="/logout" class="kicker signed-in">Signed in as ${esc(email)} ·
  <button type="submit" class="link-button">Sign out</button></form>
${sections}${loose}
${!sections && !loose ? "<p>No documents have been posted yet.</p>" : ""}`);
}

function renderFolder(folder, level) {
  const h = Math.min(level, 4);
  const inner = (folder.files.length ? fileList(folder.files) : "") +
    folder.folders.map((f) => renderFolder(f, level + 1)).join("");
  return `<h${h}>${esc(folder.name)}</h${h}>${inner || "<p class=\"kicker\">Nothing here yet.</p>"}`;
}

function fileList(files) {
  // Newest first: CMA file names carry dates (e.g. cma-meeting-minutes-2026-07).
  const sorted = [...files].sort((a, b) => b.name.localeCompare(a.name, undefined, { numeric: true }));
  const items = sorted.map((f) =>
    `<li><a href="/file/${encodeURIComponent(f.id)}" target="_blank" rel="noopener">${esc(prettyName(f.name))}</a>` +
    `<span class="doc-size">${f.size ? formatSize(Number(f.size)) : ""}</span></li>`).join("");
  return `<ul class="doc-list">${items}</ul>`;
}

function page(env, title, body, status = 200, headers = {}) {
  const site = siteUrl(env);
  return new Response(`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${esc(title)} | Coolfont Mountainside Association</title>
<link rel="stylesheet" href="${site}/assets/site.css">
<link rel="icon" href="${site}/assets/favicon.png">
<style>
.signed-in { display: flex; gap: 6px; align-items: center; }
.link-button { background: none; border: 0; padding: 0; color: var(--brand); text-decoration: underline; cursor: pointer; font: inherit; }
.members { max-width: 760px; font-size: 1.15rem; }
.members .search input, .members .search button { font-size: 1.15rem; padding: 12px 16px; }
.members .search input { max-width: 420px; }
.members .kicker { font-size: 1rem; }
</style>
</head>
<body>
<header class="site-header">
  <div class="wrap header-row"><a class="site-title" href="${site}/">Coolfont Mountainside Association</a></div>
</header>
<main id="main" class="wrap"><div class="content members">${body}
<p class="kicker" style="margin-top:2rem"><a href="${site}/">← Back to the main website</a></p></div></main>
</body>
</html>`, { status, headers: { "Content-Type": "text/html; charset=utf-8", ...headers } });
}

function redirect(location, headers = {}) {
  return new Response(null, { status: 303, headers: { Location: location, ...headers } });
}

function withSecurityHeaders(response, env) {
  const r = new Response(response.body, response);
  const site = new URL(siteUrl(env)).origin;
  r.headers.set("Cache-Control", "private, no-store");
  r.headers.set("Referrer-Policy", "no-referrer");
  r.headers.set("X-Content-Type-Options", "nosniff");
  r.headers.set("X-Robots-Tag", "noindex, nofollow");
  if ((r.headers.get("Content-Type") || "").startsWith("text/html")) {
    r.headers.set("Content-Security-Policy",
      `default-src 'none'; style-src ${site} 'unsafe-inline'; img-src ${site} data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`);
  }
  return r;
}

// ---------- Google: member list and Drive ----------

let memberCache = { at: 0, set: null };
async function members(env) {
  if (memberCache.set && Date.now() - memberCache.at < CACHE_MS) return memberCache.set;
  const res = await google(env,
    `https://sheets.googleapis.com/v4/spreadsheets/${env.MEMBER_SHEET_ID}/values/A:A?majorDimension=COLUMNS`);
  const column = ((await res.json()).values || [[]])[0] || [];
  const set = new Set(column.map(normalizeEmail).filter(Boolean)); // header row "email" isn't an address, so it drops out
  memberCache = { at: Date.now(), set };
  return set;
}

let treeCache = { at: 0, tree: null, files: null };
async function driveTree(env) {
  if (treeCache.tree && Date.now() - treeCache.at < CACHE_MS) return treeCache;
  const files = new Map();
  async function walk(folderId, depth) {
    const node = { folders: [], files: [] };
    for (const item of await listFolder(env, folderId)) {
      if (item.mimeType === FOLDER) {
        if (depth < 4) node.folders.push({ name: item.name, ...(await walk(item.id, depth + 1)) });
      } else {
        node.files.push(item);
        files.set(item.id, item);
      }
    }
    return node;
  }
  const tree = await walk(env.DRIVE_FOLDER_ID, 1);
  tree.folders.sort((a, b) => a.name.localeCompare(b.name));
  treeCache = { at: Date.now(), tree, files };
  return treeCache;
}

async function listFolder(env, folderId) {
  const items = [];
  let pageToken = "";
  do {
    const q = encodeURIComponent(`'${folderId}' in parents and trashed = false`);
    const fields = encodeURIComponent("nextPageToken, files(id, name, mimeType, size, modifiedTime)");
    const res = await google(env, `https://www.googleapis.com/drive/v3/files?q=${q}&fields=${fields}` +
      `&pageSize=1000&supportsAllDrives=true&includeItemsFromAllDrives=true${pageToken ? `&pageToken=${pageToken}` : ""}`);
    const data = await res.json();
    items.push(...(data.files || []));
    pageToken = data.nextPageToken || "";
  } while (pageToken);
  return items;
}

async function serveFile(env, id) {
  // Only files inside the shared folder are served, even if the robot account can see others.
  const file = (await driveTree(env)).files.get(id);
  if (!file) return page(env, "Not found", '<p>That document isn\'t available. <a href="/">Back to Owner Documents</a></p>', 404);
  const isGoogleDoc = file.mimeType.startsWith("application/vnd.google-apps.");
  const url = isGoogleDoc
    ? `https://www.googleapis.com/drive/v3/files/${id}/export?mimeType=application/pdf`
    : `https://www.googleapis.com/drive/v3/files/${id}?alt=media&supportsAllDrives=true`;
  const res = await google(env, url);
  const name = isGoogleDoc ? `${file.name}.pdf` : file.name;
  return new Response(res.body, {
    headers: {
      "Content-Type": isGoogleDoc ? "application/pdf" : (file.mimeType || "application/octet-stream"),
      "Content-Disposition": `inline; filename*=UTF-8''${encodeURIComponent(name)}`,
    },
  });
}

let googleToken = { value: "", exp: 0 };
async function googleAccessToken(env) {
  if (googleToken.value && Date.now() < googleToken.exp) return googleToken.value;
  const sa = JSON.parse(env.GOOGLE_SERVICE_ACCOUNT_JSON);
  const now = Math.floor(Date.now() / 1000);
  const header = b64urlJson({ alg: "RS256", typ: "JWT" });
  const claims = b64urlJson({
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/spreadsheets.readonly",
    aud: "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  });
  const der = Uint8Array.from(atob(sa.private_key.replace(/-----[^-]+-----|\s/g, "")), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, enc.encode(`${header}.${claims}`));
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=${encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer")}&assertion=${header}.${claims}.${b64url(sig)}`,
  });
  if (!res.ok) throw new Error(`Google token ${res.status}: ${await res.text()}`);
  const data = await res.json();
  googleToken = { value: data.access_token, exp: Date.now() + (data.expires_in - 120) * 1000 };
  return googleToken.value;
}

async function google(env, url) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${await googleAccessToken(env)}` } });
  if (!res.ok) throw new Error(`Google API ${res.status} for ${url.split("?")[0]}: ${await res.text()}`);
  return res;
}

// ---------- signed tokens and codes ----------

let hmacKey = null;
async function secretKey(env) {
  if (!hmacKey) {
    hmacKey = await crypto.subtle.importKey("raw", enc.encode(env.SESSION_SECRET),
      { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  }
  return hmacKey;
}

async function makeToken(env, type, email, seconds) {
  const payload = b64urlJson({ t: type, e: email, x: Math.floor(Date.now() / 1000) + seconds });
  const sig = await crypto.subtle.sign("HMAC", await secretKey(env), enc.encode(payload));
  return `${payload}.${b64url(sig)}`;
}

async function verifyToken(env, token, type) {
  const dot = token.lastIndexOf(".");
  if (dot < 1) return null;
  const payload = token.slice(0, dot);
  let sig;
  try {
    sig = fromB64url(token.slice(dot + 1));
  } catch {
    return null;
  }
  if (!(await crypto.subtle.verify("HMAC", await secretKey(env), sig, enc.encode(payload)))) return null;
  try {
    const data = JSON.parse(new TextDecoder().decode(fromB64url(payload)));
    return data.t === type && data.x > Date.now() / 1000 ? data : null;
  } catch {
    return null;
  }
}

async function codeFor(env, email, slot) {
  const sig = await crypto.subtle.sign("HMAC", await secretKey(env), enc.encode(`code|${email}|${slot}`));
  return String(new DataView(sig).getUint32(0) % 1000000).padStart(6, "0");
}

async function allowed(limiter, key) {
  if (!limiter) return true; // rate-limit binding missing (e.g. local testing)
  const { success } = await limiter.limit({ key });
  return success;
}

// ---------- small helpers ----------

function siteUrl(env) {
  return String(env.SITE_URL || "").replace(/\/$/, "");
}

function normalizeEmail(value) {
  const email = String(value || "").trim().toLowerCase();
  return /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$/.test(email) ? email : "";
}

function prettyName(name) {
  return name.replace(/\.(pdf|docx?|xlsx?|m4a|mp3|mp4|pps|zip)$/i, "").replace(/[-_]+/g, " ");
}

function formatSize(bytes) {
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function b64url(bytes) {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlJson(obj) {
  return b64url(enc.encode(JSON.stringify(obj)));
}

function fromB64url(s) {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}
