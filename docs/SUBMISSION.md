# Push the project to ELEV15

The local `main` branch is based on the existing `origin/main` history, and
`origin` points to `https://github.com/ELEVATE-1-0/ELEV15.git`.
The destination was verified as private during preparation. Nothing has been pushed.

## Submit from PowerShell

Open PowerShell in the project directory, then run:

```powershell
git status
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Add Rally racket intelligence project"
git pull --rebase origin main
git push -u origin main
```

Review the staged file list before committing. Virtual environments (`.venv*`),
`data/`, downloaded model binaries, `frontend/node_modules/`, `frontend/dist/`,
environment secrets and compiler caches are excluded. Source code, dependency
lockfiles, documentation images and `weights/manifest.json` are included.

If Git asks for your identity, configure your own name and GitHub-associated email
for this repository, then repeat the commit:

```powershell
git config user.name "Your Name"
git config user.email "your-email@example.com"
```

If authentication is requested, sign into the GitHub account that has access to
ELEVATE-1-0/ELEV15 using Git Credential Manager's browser prompt, or run
`gh auth login` followed by `gh auth setup-git`. Accept any pending organization
invitation first. Do not put tokens into the remote URL or project files.

If the pull reports conflicts, resolve them before pushing (or use
`git rebase --abort` to return to the pre-pull state). Do not force-push.
If branch protection requires a pull request, after committing run:

```powershell
git switch -c submission/rally-intelligence
git push -u origin submission/rally-intelligence
```

Then open a pull request into `main` on GitHub. Once uploaded, confirm the source
files are visible in the private repository. Reviewers should follow the fresh
installation section in the README to install dependencies and download models.

## Local checks

```powershell
.venv/Scripts/python.exe -m pytest -q -c backend/pytest.ini backend/tests
npm.cmd --prefix frontend run build
```

These checks do not require uploading match videos or model weights. The optional
real-model smoke test has extra clip requirements documented in the README.
