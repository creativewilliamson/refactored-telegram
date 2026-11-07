# Deploying VetsEatFree to Cloudflare Pages

This is J.Will's step. The build never deploys anything by itself.

The site is plain static files in `dist/`. Cloudflare Pages serves them for
free. There is no server and no database.

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

## 1. First deploy (pick ONE way)

### Way A: drag and drop in the Cloudflare dashboard (simplest)

1. Sign in at https://dash.cloudflare.com.
2. Left menu: **Workers & Pages** > **Create** > **Pages** tab >
   **Upload assets** (sometimes shown as "Use direct upload").
3. Project name: `vetseatfree` (this gives https://vetseatfree.pages.dev).
4. Drag the whole `dist` folder onto the upload box. Wait for "Success".
5. Click **Deploy site**. Open https://vetseatfree.pages.dev and search 46052.

Later deploys: **Workers & Pages** > `vetseatfree` > **Create deployment** >
drag `dist` again.

### Way B: Wrangler (command line)

Needs Node.js. One time only:

```powershell
npx wrangler login
```

Every deploy:

```powershell
npx wrangler pages deploy dist --project-name vetseatfree --branch main
```

The first run asks to create the project; say yes and pick production
branch `main`.

### Way C: connect a GitHub repo

1. Push this folder to a GitHub repo (`dist/` is not committed, so Pages
   must not build it; use Way A or B for the files, or set up a GitHub
   Action that runs the Docker build and then `wrangler pages deploy`).
2. Because the build needs Docker and a data download, Ways A and B are
   the easier choice for this site.

## 2. Check the live site (5 minutes)

- https://vetseatfree.pages.dev/ shows the search box.
- Search 46052: results load; Large-print list works.
- Open https://vetseatfree.pages.dev/near/46052 directly: results load.
  (If you get a 404 or a redirect loop there, edit `dist/_redirects` so the
  line reads `/near/* /near/ 200`, redeploy, and tell the builder.)
- Open https://vetseatfree.pages.dev/state/in/ and /about/.
- In the browser's developer tools > Network, searching sends no requests
  to anyone but vetseatfree.pages.dev.

## 3. Custom domain (optional)

1. **Workers & Pages** > `vetseatfree` > **Custom domains** >
   **Set up a custom domain**.
2. Type the domain (for example `vetseatfree.org` or `www.vetseatfree.org`)
   and click **Continue**.
3. If the domain's DNS is on Cloudflare, click **Activate domain**; the
   record is added for you. If not, add the CNAME record Cloudflare shows
   (`www` -> `vetseatfree.pages.dev`) at your DNS host.
4. Wait for "Active" (usually minutes). HTTPS is automatic.
5. If you use a custom domain, change `SITE_URL` in `pipeline/config.py`
   to it and rebuild, so the sitemap, canonical links and share image
   point at the new address.

## 4. Turn on Web Analytics (optional)

The site has no analytics code of its own. Cloudflare Web Analytics is
cookie-free.

1. **Workers & Pages** > `vetseatfree` > **Metrics** > **Web Analytics** >
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
docker compose run --rm build; if ($LASTEXITCODE -eq 0) { npx wrangler pages deploy dist --project-name vetseatfree --branch main }
```

If someone reports a store that is closed or not open yet, add it to
`data/location-exclusions.json` with the page that shows it (see the
entries already there), then run the line above.

The daily line re-reads the offers and overrides, checks All The Places for a newer
weekly store run (it falls back to the cached files if offline), rebuilds
`dist/`, re-checks the Pages limits, and uploads only if the build passed.
Without Wrangler, run just `docker compose run --rm build` and drag `dist`
into the dashboard as in Way A.

After Nov 12, stop the daily rebuild. Vouchers (for example Texas
Roadhouse, good until May 31, 2027) keep showing their "good until" date;
everything else shows "Ended" at the bottom.
