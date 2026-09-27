# Deploying to Streamlit Community Cloud — Step-by-Step

> **Read `SECURITY_CHECKLIST.md` first.** Deployment is gated on it; every box
> is currently checked except confirming HTTPS on the live URL (step 11 below).
> Recommended configuration: **rules-only path on the cloud app** (see step 8)
> — the free tier's ~1 GB RAM cannot hold the transformer NER model.

---

## Part 0 — What you need before starting

- A **GitHub account** (the deployment source is a GitHub repo).
- A **Google AI Studio API key** — *only if* you will enable the optional LLM
  feedback layer. Skip otherwise; the app is complete without it.
- 15 minutes.

## Part 1 — Get the code onto GitHub (do this on your machine)

1. **Check what will be pushed.** The `.gitignore` already excludes: `.env`
   (your API key), `resumes/` (the CV corpus — never publish it), real CVs in
   `data/gold_set/`, `.venv/`, and caches. Verify:
   ```bash
   git status --short
   ```
   You should see project files only. **If you ever see `resumes/` or `.env`
   listed, STOP and fix `.gitignore` before continuing.**

2. **Initialize and push.** The project folder is currently *inside* a parent
   git repo; give it its own:
   ```bash
   cd "<your project folder>"
   git init
   git add .
   git commit -m "CV NLP Analyzer — initial import"
   git branch -M main
   ```
   Then create an empty repo on github.com (**Private** is fine and recommended),
   and push:
   ```bash
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

## Part 2 — Create the cloud app

3. Go to **https://share.streamlit.io** and sign in **with GitHub**.

4. Click **"Create app"** → **"Paste your GitHub repo URL"** (or authorize
   repo access and pick it from the list).

5. Fill in:
   - **Repository:** `<your-username>/<repo-name>`
   - **Branch:** `main`
   - **Main file path:** `cv_analyzer/ui/app.py`  ← exactly this
   - **Python version (Advanced settings):** pick **3.11 or newer** (3.13 works;
     torch 2.14 wheels need ≥3.10 — don't leave an old default)

6. Click **Deploy**. First build takes ~5–10 minutes (it installs torch CPU +
   ~84 pinned packages, then boots). Watch the build log; "Deployed" appears
   when done.

## Part 3 — Configure the deployment (important)

7. **Set the rules-only profile.** In the app's dashboard:
   **Manage app → ⋮ menu → Settings → Secrets**, and paste exactly:
   ```toml
   # Deployment profile: rules-only (free host, ~1 GB RAM)
   NLP_EXTRACTOR_ENABLED = false
   USE_LLM_FEEDBACK = false
   ```
   The app restarts automatically. This is the supported cloud configuration —
   the NLP toggle in the UI becomes visibly disabled with an explanation.

8. **If (and only if) you want the LLM feedback layer**, add to the same
   secrets box:
   ```toml
   GEMINI_API_KEY = "AIza..."        # paste your real key
   USE_LLM_FEEDBACK = true
   ```
   Note: the key lives in Streamlit's secrets manager, never in the repo. The
   checklist items covering redaction, `<evidence>` delimiting, verification,
   and rate limiting are implemented and tested; keep `USE_LLM_FEEDBACK=false`
   for your first public deployment and enable it after you've seen the app
   behave.

9. **(Optional) LLM demo account.** Create a throwaway login
   (e.g. a dedicated Gmail) and use that key — isolates the metered quota from
   your main account.

## Part 4 — Verify the deployment

10. **Boot check:** open the app URL, paste the sample text below into
    "Paste your CV text", click **Analyze pasted CV**:
    ```
    BUDI SANTOSO
    SUMMARY
    Excellent communicator with extensive experience.
    SKILLS
    Python, SQL
    EXPERIENCE
    Data Analyst, Acme Corp
    Jun 2021 - Present
    - Responsible for various reports.
    EDUCATION
    BSc in Statistics, 2019, GPA 3.65
    ```
    Expect: findings (vague bullet, unsupported claim, missing-section if any),
    an extraction count, and highlighted evidence in the annotated CV view.
    First analysis after a cold start may take ~30–60 s while the embedding
    model downloads (~470 MB, one time).

11. **Confirm HTTPS** — the URL must start with `https://` (Streamlit Cloud
    provides it automatically; this closes the last open item in
    `SECURITY_CHECKLIST.md`).

12. **Run the security self-checks once:** upload a random non-PDF file with
    a `.pdf` extension → expect a rejection message; upload a >5 MB file →
    expect a rejection message.

## Part 5 — Day-to-day operation

- **Every `git push` to `main` auto-redeploys.** Update code locally → commit →
  push → the cloud app rebuilds in a few minutes.
- **Reboot/redeploy:** Manage app → ⋮ → Reboot or Delete, then re-create.
- **Cold starts:** the app sleeps when idle; the first visitor after a sleep
  waits for the rebuild/boot. Warm it up before a demo or defense.
- **Logs:** Manage app → manage logs (terminal icon) — the pipeline never logs
  CV text; logs carry only platform output.

## Part 6 — When something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| `E: Unable to locate package ...` at the apt step | `packages.txt` contains comment text — the platform pipes **every line** to `apt-get install` | Keep `packages.txt` empty (0 bytes); this project needs no apt packages |
| Build fails installing torch (`No matching distribution`) | App Python version too old for `torch==2.14.0+cpu` | Re-create the app with **Python 3.11+** in "Advanced settings" (or lower the torch pin) |
| Build fails on torch | The `--extra-index-url` line was removed from `requirements.txt` | Restore the first line of requirements.txt |
| App crashes on startup | `Main file path` wrong | Must be `cv_analyzer/ui/app.py` |
| Memory error / OOM kill | NER layer enabled on the free tier | Set `NLP_EXTRACTOR_ENABLED = false` in secrets (step 7) |
| "Module cv_analyzer not found" | Wrong main file path or repo layout changed | Keep `cv_analyzer/` at the repo root; main file `cv_analyzer/ui/app.py` |
| Findings differ from local runs | Different thresholds/models on the host | Compare `report.meta["config"]` in the report against your local `.env` |
| Key invalid / quota errors | Wrong key or Gemini quota exhausted | Check the key in secrets; the app fails closed to templates regardless |

## Part 7 — What NOT to deploy

- The `resumes/` corpus must never appear in the public repo.
- `.env` must never be committed — the secrets manager replaces it.
- Do not enable the NER layer on Streamlit Cloud's free tier (OOM).
- Do not commit real people's CVs; the gold scaffold + synthetic fixtures only.

## Alternative hosts (if you outgrow the free tier)

- **Render / Railway**: Docker-based; can ship the full NER path; free tiers
  still sleep; HTTPS by default. Requires a Dockerfile (not in this repo yet).
- **Hugging Face Spaces**: free CPU tier, academically nice co-location with
  the models used; same ~1 GB RAM constraint as Streamlit Cloud.
- **Avoid**: PythonAnywhere (no torch on free), any host without HTTPS.
