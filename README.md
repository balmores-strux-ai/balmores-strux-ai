# BALMORES STRUX AI

Chat-style structural assistant: plain English → 3D frame, linear FEM, drift check, graphs, ETABS-oriented text export.

## Local run

See `START_HERE.txt` or:

```bash
pip install -r requirements.txt
copy .env.example .env   # add OPENAI_API_KEY
uvicorn app:app --host 127.0.0.1 --port 8000
```

## Deploy on Render

1. Push this repo to **GitHub** (see below).
2. In [Render](https://render.com): **New +** → **Blueprint** → connect the repo → apply `render.yaml`.
3. In the Render dashboard, set **Environment**:
   - `OPENAI_API_KEY` — required for Build & Analyze / Ask.
   - Optional: `BALMORES_BRAIN_PT` — only if you host a small `.pt` somewhere reachable (Render disk is ephemeral; prefer bundling in image or external URL — see Render docs for persistent disk if needed).

**Note:** `.pt` brain files are gitignored by default. Train/deploy weights separately if they are large.

## Push to GitHub (on your PC)

Install [Git](https://git-scm.com/download/win) or use **GitHub Desktop**.

```bash
cd balmores-strux-ai
git init
git add .
git commit -m "Initial commit: BALMORES STRUX AI for Render"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Replace `YOUR_USER/YOUR_REPO` with your repository.

## License

Use and modify for your projects; verify all structural work with a licensed PE and ETABS (or equivalent).
