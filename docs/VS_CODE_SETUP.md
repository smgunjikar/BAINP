# Windows VS Code — step-by-step setup

## Prerequisites

Install: Git for Windows, Python 3.11/3.12, Node.js 22 LTS (or Node >=20.9), Visual Studio Code. In VS Code install Python, Pylance and ESLint extensions. Run `python --version`, `node --version`, `npm --version`, `git --version`.

## 1. Extract folder

Extract `brainsignal-nexus-v1.zip` to e.g. `C:\Projects\brainsignal-nexus-v1`, then VS Code -> File -> Open Folder.

## 2. Start backend

Terminal -> New Terminal (PowerShell, repository root):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
python -m pytest apps/api/tests -q
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Visit http://127.0.0.1:8000/demo (immediate standalone UI), http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs . You can use the standalone page even if npm packages are unavailable. The running API terminal remains open.

If `py -3.11` fails, use a locally installed compatible Python command. If activation is blocked, execute `Set-ExecutionPolicy RemoteSigned -Scope Process` in that same terminal and try activation again.

## 3. Start frontend

New Terminal (separate from API):

```powershell
cd apps/web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Visit http://localhost:3000 . Click Cognitive Lab, complete a synthetic task and confirm that the session appears. Click CareLoop, change a fictional case status and refresh.

## 4. Run the first OASIS inventory (after placing authorized data locally)

```powershell
# In the repository ROOT terminal
New-Item -ItemType Directory -Force data/raw/oasis2
# Copy authorized files from your private storage into data/raw/oasis2
python research/oasis/inventory.py --source data/raw/oasis2
```

Only aggregate extension counts will be printed. `data/raw/` is ignored by Git. Do not use a public repository or deploy these files.

## 5. Typical troubleshooting

- `ModuleNotFoundError app`: run uvicorn with `--app-dir apps/api` from root.
- React fails to connect: ensure port 8000 is running and `.env.local` points to `http://127.0.0.1:8000`.
- CORS error: browse the frontend at `http://localhost:3000`, not another host, until allowed origins are configured.
- `npm` command not recognized: reopen terminal after installing Node.
- PowerShell scripts disabled: `Set-ExecutionPolicy RemoteSigned -Scope Process` affects the current terminal only.
- Model imports missing: install *research-specific* dependencies in a separate environment; do not add large MRI/EEG dependencies to the web/API runtime.
