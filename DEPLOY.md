# Deploying Vet Day Deals to Cloudflare Pages

This is J.Will's step. The build never deploys anything by itself.

The site is plain static files in `dist/`. Cloudflare Pages serves them for
free. There is no server and no database.

- Site name: **Vet Day Deals**
- Cloudflare Pages project name: **`vetdaydeals`**
- Address: **https://vetdaydeals.pages.dev**

(The project folder is still called `vetseatfree-finder`; only the folder
keeps that name. Nothing in `dist/` uses it.)

## 0. Build `dist/` first

In PowerShell, in this folder:

```powershell
docker compose run --rm build
```

It ends with a line like:

```
Cloudflare Pages check: 3114 files (limit 20,000), largest 251 KB (limit 25 MiB). OK
Built dist/
```

If either Pages limit is ever exceeded, the build stops with
`BUILD FAILED` and nothing should be uploaded.

Check it locally before you upload: `.\start.ps1`, then open
http://localhost:8095/ and search 46052. Also open
http://localhost:8095/near/46052 directly; it must show results.

## 1. First deploy: Wrangler (the main way)

Use Wrangler, Cloudflare's command-line tool. The site has about 3,100
files, and Wrangler uploads up to 20,000.

Needs Node.js. One time only:

```powershell
npx wrangler login
```

Every deploy:

```powershell
npx wrangler pages deploy dist --project-name vetdaydeals --branch main
```

The first run asks to create the project `vetdaydeals`; say yes and pick
production branch `main`. When it finishes, open
https://vetdaydeals.pages.dev and search 46052.

### Why not drag and drop in the dashboard?

Cloudflare's dashboard upload (**Workers & Pages** > **Create** > **Pages** >
**Upload assets**) is limited to **1,000 files** per drag-and-drop upload.
This site has about 3,100, so a drag-and-drop upload would be refused or
come out incomplete. Only use the dashboard to look at the project
(`vetdaydeals`), its deployments and its settings, not to upload `dist`.

### Not recommended: connecting a GitHub repo

Pages can build from a GitHub repo, but this site's build needs Docker and
a data download, which Pages' own builder doesn't run. `dist/` is not
committed. If you ever want automatic deploys, set up a GitHub Action that
runs the Docker build and then the same
`wrangler pages deploy dist --project-name vetdaydeals --branch main` line.

## 2. Check the live site (5 minutes)

- https://vetdaydeals.pages.dev/ shows the search box.
- Search 46052: results load; Large-print list works; **New search** goes
  back to the search box.
- Open https://vetdaydeals.pages.dev/near/46052 directly: results load.
  (If you get a 404 or a redirect loop there, edit `dist/_redirects` so the
  line reads `/near/* /near/ 200`, redeploy, and tell the builder.)
- Open https://vetdaydeals.pages.dev/state/in/ and /about/.
- In the browser's developer tools > Network, searching sends no requests
  to anyone but vetdaydeals.pages.dev.

## 3. Custom domain (optional)

1. **Workers & Pages** > `vetdaydeals` > **Custom domains** >
   **Set up a custom domain**.
2. Type the domain (for example `vetdaydeals.org` or `www.vetdaydeals.org`)
   and click **Continue**.
3. If the domain's DNS is on Cloudflare, click **Activate domain**; the
   record is added for you. If not, add the CNAME record Cloudflare shows
   (`www` -> `vetdaydeals.pages.dev`) at your DNS host.
4. Wait for "Active" (usually minutes). HTTPS is automatic.
5. If you use a custom domain, change `SITE_URL` in `pipeline/config.py`
   to it and rebuild, so the sitemap, canonical links and share image
   point at the new address.

## 4. Turn on Web Analytics (optional)

The site has no analytics code of its own. Cloudflare Web Analytics is
cookie-free.

1. **Workers & Pages** > `vetdaydeals` > **Metrics** > **Web Analytics** >
   **Enable**. Cloudflare adds its beacon automatically on each deploy.
2. The site's security header only allows its own scripts. For the beacon
   to load, edit `pipeline/build.py`, in the `csp = (...)` line add
   `https://static.cloudflareinsights.com` after `script-src 'self'` and
   `https://cloudflareinsights.com` after `connect-src 'self'`, rebuild
   and redeploy.
3. Update the About page privacy text if you turn it on
   (`pipeline/templates/about.html.j2`: "No tracking" -> "Cloudflare
   counts visits without cookies").

## 5. Daily rebuild through Nov 12 (offer updates)

Each morning, after any offer corrections are added to
`data/overrides.json` (never edit `data/seed/`), run this one line in
PowerShell in this folder:

```powershell
docker compose run --rm build; if ($LASTEXITCODE -eq 0) { npx wrangler pages deploy dist --project-name vetdaydeals --branch main }
```

If someone reports a store that is closed or not open yet, add it to
`data/location-exclusions.json` with the page that shows it (see the
entries already there), then run the line above.

The daily line re-reads the offers and overrides, checks All The Places for a newer
weekly store run (it falls back to the cached files if offline), rebuilds
`dist/`, re-checks the Pages limits, and uploads only if the build passed.

After Nov 12, stop the daily rebuild. Vouchers (for example Texas
Roadhouse, good until May 31, 2027) keep showing their "good until" date;
everything else shows "Ended" at the bottom.
