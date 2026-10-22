---
name: deploy-survivortiers
description: Deploys the SurvivorTiers static site (site/) to Cloudflare Pages production (survivortiers.pages.dev) from a clean main, then verifies the live pages and submits IndexNow. Use when the user says deploy, desplegar, despliega, publish, publicar, push to production, or mentions wrangler, Cloudflare, Pages, or survivortiers.pages.dev.
---

# Deploy survivortiers

Production is **Cloudflare Pages**, project `survivortiers`, production branch `main`, serving `https://survivortiers.pages.dev`.

## Non-negotiables

- **Never run `npx wrangler deploy`.** It uploads a Worker version (`wrangler.jsonc`), not the site. The Worker has no routes, so it publishes nothing public, but it changes the Worker's active version. On 2026-10-22 this happened by mistake and had to be rolled back with `npx wrangler rollback 3d684202-7979-456f-95f3-a8e06421cd66`.
- **`pokesurvivor.com` is the game, not this site.** It belongs to the game repo `JPTER78/pokesurvivor`. Do not look for the site there.
- Do not use `vercel.json` or the Vercel CLI for this site.
- Deploy only from a clean `main` that matches the merged PR. Never deploy from a feature branch.

## Steps

1. **Sync main and check it is clean**

   ```sh
   git checkout main && git pull --ff-only origin main && git status --short
   ```

   `git status` must be empty. If it is not, stop and ask. The last commit must be the merged PR.

2. **Tests (Python 3.12 only)**

   The system `python3` is 3.9, and `render.py` fails there. Always go through `uv`:

   ```sh
   uv run --python 3.12 python -m unittest discover -s build -p "test_*.py"
   ```

3. **Render with no sprite override**

   ```sh
   echo "SPRITE_BASE=${SPRITE_BASE:-<unset>}"   # must print <unset>
   uv run --python 3.12 python3 build/render.py
   ```

   The last line should be `render: N archivos ... → .../site`.

4. **Check the built site locally**

   The local server dies when a shell call ends. Start it, run the checker, and stop it in the same command:

   ```sh
   uv run --python 3.12 python3 build/serve.py --port 8790 & SP=$!
   for i in $(seq 1 20); do sleep 1; [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8790/)" = "200" ] && break; done
   uv run --python 3.12 python3 build/check_site.py http://127.0.0.1:8790/
   kill $SP
   ```

   It must end with `Todo correcto.`

   For visual checks, the in-app browser cannot reach `127.0.0.1`. Use Playwright in the same command as the server:

   ```sh
   uv run --python 3.12 --with playwright python -m playwright screenshot --viewport-size 1280,900 --full-page http://127.0.0.1:8790/naturalezas.html /tmp/x.png
   ```

   Use `390,844` for mobile.

5. **Deploy to Pages production**

   ```sh
   npx --yes wrangler pages deploy site --project-name survivortiers --branch main --commit-dirty=false
   ```

   The output ends with `Deployment complete! ... https://<hash>.survivortiers.pages.dev`. Pages uploads only new files, so a repeat deploy is quick.

6. **Verify live**

   Pages returns `308` from `x.html` to the clean URL. Follow redirects with `curl -L`:

   ```sh
   B=https://survivortiers.pages.dev
   for u in / /naturalezas /en/naturalezas /pasivas /pokemon/1-bulbasaur/; do
     echo "$u -> $(curl -sL -o /tmp/p.html -w '%{http_code}' $B$u) $(rg -o '<title>[^<]*</title>' /tmp/p.html | head -1)"
   done
   ```

   Every line must be `200`, with the expected title. Also check one content string that only the new build has.

7. **IndexNow (documented after every deploy)**

   The key file must answer first: `curl -s -o /dev/null -w '%{http_code}' $B/7fdc3539a344d6657d3ef1d62732da7c.txt` should print `200`. Then:

   ```sh
   uv run --python 3.12 python3 build/indexnow.py --dry-run
   uv run --python 3.12 python3 build/indexnow.py
   ```

   It should print `lote 1: HTTP 200`.

8. **Report to the user**

   Give the deployment URL, the live URLs checked, and the commit on `main`. Say what was not deployed or verified.

## Changes that need a PR first

Code and content changes go through a branch and a PR, which is then merged to `main`. Deploy after the merge. Use `gh pr checks <n> --watch --interval 20` to wait for CI, then `gh pr merge <n> --squash`.

## Rolling back a bad deploy

Redeploy the last good commit: check it out in a detached worktree, render, and run the Pages deploy from step 5. Do not use `wrangler deploy` for this.
