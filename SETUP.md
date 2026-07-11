# Setup — your animated GitHub profile

This repo generates a neofetch-style card (ASCII portrait + live stats) that
shows on your GitHub profile. Follow these steps once.

## 1. Create the special repo
On GitHub, create a **public** repo named **exactly** your username:

    charithkapuluru/charithkapuluru

(A repo whose name matches your username is what GitHub renders on your profile.)

## 2. Add these files
Upload everything in this folder to that repo, keeping the structure:

    today.py
    requirements.txt
    README.md
    dark_mode.svg          <- placeholders until step 4 runs
    light_mode.svg
    cache/.gitkeep
    .github/workflows/main.yml

## 3. Create a Personal Access Token (needed for the private/commit stats)
1. GitHub -> Settings -> Developer settings -> Personal access tokens ->
   **Tokens (classic)** -> Generate new token (classic).
2. Scopes: check **repo** and **read:user**.
3. Generate, then copy the token (you only see it once).
4. In your repo: Settings -> Secrets and variables -> Actions -> New repository
   secret. Name it **ACCESS_TOKEN**, paste the token, save.

## 4. Run it once
Go to the **Actions** tab -> enable workflows if prompted -> open
"Update profile SVGs" -> **Run workflow**. In ~1-2 minutes it fetches your real
numbers and overwrites the placeholder SVGs. After that it refreshes on its own
twice a day.

## 5. Personalize the text (optional)
Open **today.py** and edit the `INFO` dictionary near the top — OS, host,
languages, hobbies, contact. A few fields I guessed; please confirm:
  - "host"      -> currently "CBRE - Digital & Technology (Incoming)"
  - "kernel"    -> your role line
  - "linkedin"  -> currently "charithkapuluru" (set your real handle)
`BIRTHDAY` is set to 2002-01-30 (drives the live "Uptime" line).

## Notes
- The `++`/`--` lines-of-code counter is best-effort: it sums additions and
  deletions you authored across your repos and caches results in `cache/` so
  later runs are fast. The very first run can take a few minutes on big accounts.
- If a stat looks off, it's almost always token scopes — regenerate the token
  with `repo` + `read:user`.

## Fastest path: deploy.sh
If you have the GitHub CLI (`gh`) installed and have run `gh auth login`,
just run from this folder:

    bash deploy.sh

It creates the repo, sets the ACCESS_TOKEN secret (it will prompt you to paste
your token), pushes everything, and runs the workflow — no manual steps beyond
login + pasting the token once.
