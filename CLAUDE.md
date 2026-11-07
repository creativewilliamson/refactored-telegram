# Builder rules — app build loop

You are building the app described in GOAL.md, one feature at a time.
Don't stop to ask questions: decide, note the decision in PROGRESS.md,
and keep going. If the user is watching, they will steer by message or
through STEER.md.

## First turn only: set up the app
If there is no `start.ps1` yet, the app hasn't been set up. Do this
first, then continue with the normal turn:
- Read everything in `reference\` (start with `reference\README.md`,
  open every image). Write 3-6 lines in PROGRESS.md on what you took
  from it: layout, sections, look, anything that shapes the build.
- `git init` (if needed) and a `.gitignore`.
- Pick the stack: Python whenever plausible. If you choose something
  else, say why in PROGRESS.md.
- `Dockerfile` and `docker-compose.yml`. The app runs in Docker.
- `start.ps1`: runs `docker compose up --build -d`, waits until the app
  answers, and prints the URL to open.
- A bare app shell that `start.ps1` launches and a browser can open.
  Run it once and confirm.
- Commit: "Run 1: setup."

## Every turn starts the same way
1. If `AGENT_STOP` exists in the project root: write RUN-REPORT.md,
   commit, and stop.
2. If `STEER.md` has content: follow it, note that in PROGRESS.md, then
   empty the file.
3. Read PROGRESS.md, `git log --oneline -15`, and FEATURES.json.
4. Run `start.ps1` and click through the features already passing. If
   anything is broken, fix it before new work. Skip features marked
   `"retired": true` everywhere; they describe behavior that was
   deliberately replaced.

## Then build ONE feature
5. Pick the highest-priority feature with `"passes": false` that is not
   retired.
6. Build it. Keep the code clean enough to merge. If the feature has a
   screen, check it against the matching file in `reference\`.
7. Test it the way a user would, in the browser with Playwright. Save a
   screenshot to `evidence/<feature-id>.png`. Unit tests alone don't
   count.
8. Open the evidence. Only then change that feature's `"passes"` to
   true. That is the ONLY edit allowed in FEATURES.json: never delete,
   reword, or add features.
9. Commit: "<feature-id>: <what changed>". Append 2–4 lines to
   PROGRESS.md: what you did, what you decided, what's next.
10. Print in your reply: the feature id, the test result, and the
    evidence path. The goal checker can only see what you print.

If a feature won't work after 3 honest attempts, mark it stubbed in
PROGRESS.md, commit, and move on. Don't fake a pass.

## When every feature passes
11. Run the evaluator subagent (`evaluator`) on the whole app, in the
    foreground: wait for its verdict in this turn, never start it as a
    background task. Print its verdict.
12. If NEEDS_WORK: add its blocking findings to PROGRESS.md as work
    items, fix them the same way (steps 6–10), then run the evaluator
    again. Don't fix items it lists as Polish; put them under Known bugs
    in RUN-REPORT.md.
13. If PASS: write RUN-REPORT.md (format below), commit, print
    "RUN-REPORT.md written; evaluator PASS".

## Hard rules
- Python whenever plausible; the app runs in Docker.
- Data — this app's approved exception to "sample data only": use real
  PUBLIC data only (the offer seed, All The Places, Census files, and
  hand-entered single locations with a source). Business names appear as
  plain text. Never logos or brand images. No confidential, personal or
  work data, credentials, or API keys.
- Never invent an offer, location, phone number or hour. Every offer
  links to its source_url.
- Never edit `data/seed/`. Corrections go in `data/overrides.json`, each
  with a `reason` and a `source_url`.
- The visitor's ZIP, city and location never leave their device. All
  distance math runs in the browser. No cookies, no third-party scripts,
  no tracking.
- Never deploy, never `git push`, never run `wrangler`. Deploying is
  J.Will's step (DEPLOY.md).
- Never read, write, or delete anything outside this project folder.
- The app serves on http://localhost:8095. Never bind port 8080, and
  never stop, remove or change Docker containers, images or volumes that
  aren't this project's own (another project is running on 8080).
- No Microsoft products or services.
- Commit at every milestone. If a change breaks the app, `git revert` it.
- When reference/SPEC.md doesn't cover a choice, pick what works best for
  an older, rural veteran on a slow phone, and note it in PROGRESS.md.

## RUN-REPORT.md format
# Run report — <app> — <date and time>
**Run ended by:** done bar met / time limit / turn limit / AGENT_STOP
**Start it:** `.\start.ps1`, then open <url>
## Try these
<one line per core flow: what to click and what you should see>
## Status
Done: <features> | Stubbed: <features + why> | Failed: <features + why>
## Known bugs
## Evaluator's last verdict
## Suggested next goal
