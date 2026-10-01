---
name: Python ML dependency setup
description: Replit package installation behavior for this mixed pnpm and Python workspace.
---

Keep deployment dependency files separated: the workspace-root `requirements.txt` is Streamlit Community Cloud's frontend dependency entry point, while Flask and model runtime packages belong in `backend/requirements.txt`. Replit's Python package installation callback may append installed packages to the root requirements file; restore that file after environment setup so the frontend deployment does not install PyTorch unnecessarily.

**Why:** Installing ML packages through the workspace package manager rewrote the root requirements entry point, and a pinned PyTorch wheel was rejected by the package firewall while the latest unpinned package installed successfully.

**How to apply:** After adding or installing Python packages in this workspace, inspect the root and backend requirements files, preserve separate frontend/backend dependency sets, and use an unpinned compatible PyTorch package if an older pinned wheel is blocked.