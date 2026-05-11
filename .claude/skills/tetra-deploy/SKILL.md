---
name: tetra-deploy
description: Build, ship, and smoke-test a code change to the live dotbooks.store deployment (tetra → Coolify → Cloudflare). Use after committing to main when the user asks to "deploy", "ship", or "push to prod".
---

# tetra-deploy

Trigger phrases: **"deploy to tetra"**, **"ship to prod"**, **"push to dotbooks"**.

## Stack

Cloudflare (Full) → Plesk vhost → Coolify Traefik (HTTPS:8445) → web
container (Morpheus). Live app UUID `ghtnqf6lw2bg5229lv1sf4h9` per
user's auto-memory.

## Steps

1. **Confirm clean tree.** `git status` shows no uncommitted changes,
   no untracked source files. If dirty, ask the user before
   continuing.
2. **rsync the working copy to tetra** (the GHCR build path is
   currently billing-locked, so we build on the server):

   ```bash
   rsync -avz --delete \
     --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
     --exclude='node_modules' --exclude='vendor/vibe-skills' \
     -e "$HOME/.ssh/tetra-ssh.sh ssh" \
     ./ tetra:/home/morpheus-src/
   ```

   The wrapper script `~/.ssh/tetra-ssh.sh` already handles the
   Plesk-PAM-blocked auth (password lives in macOS Keychain).
3. **Build + cycle on tetra**:

   ```bash
   ~/.ssh/tetra-ssh.sh "cd /home/morpheus-src && \
     docker build -t morpheus-web:latest . && \
     docker compose up -d --no-build --force-recreate web && \
     docker exec web-ghtnqf6lw2bg5229lv1sf4h9 python manage.py migrate --noinput && \
     docker exec web-ghtnqf6lw2bg5229lv1sf4h9 python manage.py collectstatic --noinput"
   ```

4. **Smoke test the public URL**. A passing build is necessary, not
   sufficient — hit the actual edge:

   ```bash
   curl -sI https://dotbooks.store/ | head -5
   curl -sI https://dotbooks.store/dashboard/ | head -5
   curl -s https://dotbooks.store/.well-known/ucp.json | head -20
   ```

   Each must return a 2xx (or expected redirect). If a 502 appears,
   diagnose the proxy chain top-down (Cloudflare → Plesk → Traefik →
   container) using the chain reference in user memory.

5. **Tail logs for 30s** to catch boot-time exceptions:

   ```bash
   ~/.ssh/tetra-ssh.sh "docker logs --tail 50 web-ghtnqf6lw2bg5229lv1sf4h9"
   ```

6. **Report honestly.** Say what shipped, what didn't, what's left.
   A 200 from the homepage doesn't prove the feature you added works
   — test the actual feature in a browser.

## When NOT to use

- For unmerged work — deploy main, not feature branches.
- When the user has not asked. This skill never fires unprompted.
- Database migrations that drop columns or rename tables — confirm
  with the user before the docker exec migrate step.

## See also

- User memory: `dotbooks_proxy_chain.md`, `coolify_access.md`.
- [docs/deploy-coolify.md](../../../docs/deploy-coolify.md).
