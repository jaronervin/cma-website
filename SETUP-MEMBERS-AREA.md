# Members area setup (email sign-in + Google Drive)

One-time setup for the members-only Owner Documents area. All accounts below are free.
**Secrets (keys and tokens) go only into GitHub Secrets.** Never paste them into chat, email, or any file in this folder.

Where secrets go: https://github.com/jaronervin/cma-website/settings/secrets/actions → **New repository secret**

| Secret name | From step |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | 1 |
| `CLOUDFLARE_API_TOKEN` | 1 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 2 |
| `RESEND_API_KEY` | 3 |
| `SESSION_SECRET` | 4 |

---

## 1. Cloudflare (runs the sign-in "gatekeeper")

1. Sign up: https://dash.cloudflare.com/sign-up, then confirm the email Cloudflare sends.
2. Open **Workers & Pages**: https://dash.cloudflare.com/?to=/:account/workers-and-pages
   - If asked to pick a **workers.dev subdomain**, choose something like `coolfont`. The gatekeeper will live at `cma-members.<your-subdomain>.workers.dev` for the demo.
   - Choose the **Free** plan if asked.
3. **Account ID:** on that same Workers & Pages page, copy **Account ID** from the right-hand side
   (or from the account home page's menu next to the account name → *Copy account ID*).
   Save it as the GitHub secret `CLOUDFLARE_ACCOUNT_ID`. (Not truly secret, but it's tidy to keep it there.)
4. **API token:** https://dash.cloudflare.com/profile/api-tokens → **Create Token** → use the **Edit Cloudflare Workers** template →
   *Account Resources*: your account; *Zone Resources*: All zones → **Continue to summary** → **Create Token**.
   Copy the token (it's shown only once) and save it as `CLOUDFLARE_API_TOKEN`.

## 2. Google Cloud "robot account" (lets the gatekeeper read Drive)

Use the same Google account that owns the Drive folder.

1. Create a project: https://console.cloud.google.com/projectcreate. Name it `CMA Website`, then **Create**.
   No billing account is needed. Make sure `CMA Website` is the selected project (top bar) for the next steps.
2. Turn on two APIs (click **Enable** on each):
   - Google Drive API: https://console.cloud.google.com/apis/library/drive.googleapis.com
   - Google Sheets API: https://console.cloud.google.com/apis/library/sheets.googleapis.com
3. Create the robot (service) account: https://console.cloud.google.com/iam-admin/serviceaccounts/create
   - Name: `cma-docs-reader` → **Create and continue** → skip the optional role and user steps → **Done**.
   - Copy its email address. It looks like `cma-docs-reader@<project-id>.iam.gserviceaccount.com`.
4. Create its key: click the new service account → **Keys** tab → **Add key** → **Create new key** → **JSON** → **Create**.
   A `.json` file downloads (usually to your Downloads folder).
   - Open it in Notepad, select all, copy, and save the **entire contents** as the GitHub secret `GOOGLE_SERVICE_ACCOUNT_JSON`.
   - Then **delete the downloaded file** and empty the Recycle Bin. Don't move it into the Website Docs folder.
5. Give the robot view-only access, without sending a notification:
   - The Drive folder **CMA Owner Documents (demo)** → Share → paste the robot's email → **Viewer** → untick *Notify people* → Share.
   - The Sheet **CMA Member Emails (demo)** → Share → same robot email → **Viewer** → Share.

## 3. Resend (sends the sign-in emails)

1. Sign up **with the same email that's in the member list** (for the demo, `jaronervin@gmail.com`): https://resend.com/signup
   On the free plan, until a domain is verified, Resend only delivers to the account owner's own address. That's enough for the demo.
2. Create an API key: https://resend.com/api-keys → **Create API Key** → name `cma-members`, permission **Sending access** → **Add**.
   Copy it (shown once) and save it as `RESEND_API_KEY`.
3. *(Later, for real use.)* Verify `coolfontmountainside.com` at https://resend.com/domains. Resend shows a few DNS records for whoever manages the domain to add.
   No mail hosting is involved; this only proves the HOA is allowed to send from that domain.

## 4. Session secret (signs the "remember me" cookie)

From the Website Docs folder in PowerShell, run this exactly as written. It makes a random value and stores it straight in GitHub without displaying it:

```powershell
gh secret set SESSION_SECRET -R jaronervin/cma-website --body "$([guid]::NewGuid())$([guid]::NewGuid())"
```

Changing this value later signs everyone out, which is handy if it's ever needed.

## 5. Check

All five names should be listed at https://github.com/jaronervin/cma-website/settings/secrets/actions.
GitHub never shows the values again, which is expected.

Not secret, and needed to finish the build: the **robot's email address** (step 2.3) and the **workers.dev subdomain** (step 1.2).

## 6. Deploy and switch the website over

1. Deploy the gatekeeper: https://github.com/jaronervin/cma-website/actions/workflows/members.yml → **Run workflow**.
   (It also redeploys automatically whenever anything in `members/` changes.)
   Until `CLOUDFLARE_API_TOKEN` exists, the workflow just notes that it's skipping.
2. The gatekeeper's address is `https://cma-members.<subdomain>.workers.dev`. Open it and sign in with the test email.
3. Put that address in `site-src/site.json` → `owner_docs.members_url` and push. The Owner Documents page then
   shows **Sign in to Owner Documents** instead of the Google Drive link.

## How it works (for whoever maintains it)

- Code: `members/src/index.js` (one file, no dependencies). Settings: `members/wrangler.toml`.
- **Members** = email addresses in column A of the member Sheet (row 1 is the header). Changes take effect within ~5 minutes.
  Removing an address also ends that person's existing sign-ins.
- **Documents** = everything in the Drive folder (up to 4 levels of subfolders). New files appear within ~5 minutes.
  Only files inside that folder can be served, even if other files are shared with the robot account.
- Sign-in links last 30 minutes and codes 10–20 minutes. Being signed in lasts 180 days (`SESSION_DAYS`).
- To sign **everyone** out, change `SESSION_SECRET` (rerun step 4) and redeploy.
- Errors show up under the Worker's **Logs** in the Cloudflare dashboard.
