# Publish BAINP scaffold to the existing private GitHub repository

Existing repository (created by the user, shown in screenshots):

**https://github.com/smgunjikar/BAINP**

The repository currently contains a remote `README.md` on branch `main`. **Do not create another repository.** Follow the safe clone-then-copy procedure, which preserves its initial commit history.

## 1. Clone in VS Code

Press **Ctrl+Shift+P** → `Git: Clone` → paste:

```text
https://github.com/smgunjikar/BAINP.git
```

Choose a parent folder such as `C:\Users\DELL\Documents\Projects` — not an existing nonempty BAINP folder. After cloning, click **Open**. Authenticate to GitHub if prompted.

Alternative using VS Code terminal from the **parent** directory:

```powershell
git clone https://github.com/smgunjikar/BAINP.git
cd BAINP
code .
```

If you have a previously opened empty local `BAINP` folder, close it and use the newly cloned one. Avoid nesting BAINP inside BAINP.

## 2. Unpack starter files into your cloned folder

Download `BAINP-starter.zip` to Downloads. In the VS Code terminal **at the root of the cloned BAINP repo**, run:

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\BAINP-starter.zip" -DestinationPath . -Force
```

The ZIP intentionally contains **root-level** files (README.md, .gitignore, apps/, research/, docs/). `-Force` updates the existing one-line README with a full project README; it does not touch `.git` history. If your downloaded filename/path differs, change the ZIP path.

Check:

```powershell
Get-ChildItem -Force | Select-Object Name
# Expect: .git, .github, .gitignore, apps, research, data, docs, scripts, README.md
```

## 3. Verify remote and local code before pushing

```powershell
git remote -v
# Must show github.com/smgunjikar/BAINP.git
git branch --show-current
# Should show main
python scripts/check_repo.py
python -m pip install -r apps/api/requirements.txt
python -m pytest apps/api/tests research/adni/tests -q
```

Do not run `git init` again. Do not run `git push --force`.

## 4. Stage, safety-check, commit and push

```powershell
git add .
python scripts/preflight_git.py
git diff --cached --stat
git status --short
git commit -m "chore: scaffold BAINP research monorepo"
git push -u origin main
```

After push, reload `https://github.com/smgunjikar/BAINP`. You should see `apps/`, `research/`, `docs/`, `scripts/`, `.github/` and `README.md`. GitHub Actions should run the backend tests.

If push is rejected because remote changed, run `git pull --rebase origin main`, resolve any conflicts and push again. Do **not** force push.

## Common problems

- `fatal: destination path 'BAINP' already exists`: clone into a different clean parent directory, or relocate the old empty folder. Do not delete a working directory containing files without inspecting it.
- `Repository not found`: sign in to the account that owns the private repository and retry.
- `git is not recognized`: install Git for Windows, then restart VS Code.
- `python` not found: install Python 3.11 or select an existing Python 3.11 environment; use `py -3.11` on Windows.
- `npm` not found: install a supported Node.js release before frontend work.
- `running scripts is disabled`: use `cmd.exe` activation (`.venv\Scripts\activate.bat`) or follow Microsoft PowerShell execution-policy guidance. Do not indiscriminately disable system policy.
