# Start here: fresh NeuroAccess module

The previous apps/api and apps/web folders were archived during the fresh install.
They are not the running application. Research scripts, research datasets and the
old PostgreSQL database were preserved; old participants were not imported.

Activate bainp, then run:

powershell -NoProfile -ExecutionPolicy Bypass -File .\apps\neuroaccess\Start-NeuroAccess.ps1

Open http://127.0.0.1:3000 and use the local operator code printed in the terminal.
Select Active or Demo. Profiles and check-ins persist until explicitly deleted.

Stop this module: add -Service Stop to the command above.
Verify in isolated temporary data: add -Service Verify.
Read apps/neuroaccess/README.md for the architecture, storage, limitations, code
responsibilities, manual acceptance flow and Git targets.

Do not rerun old application patch installers or start the old npm/uvicorn stack.
This reset implements NeuroAccess only; C01-C06 cognitive tasks remain future work.
