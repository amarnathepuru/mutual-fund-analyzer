# FundLens — Mutual Fund Analyzer

Portfolio intelligence for Indian mutual funds: overlap, holdings, sector exposure, and portfolio X-Ray.

## Run locally

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Open **http://localhost:8501** (or double-click `run_app.bat` on Windows).

## Streamlit Cloud (GitHub deploy)

In [share.streamlit.io](https://share.streamlit.io), connect this repo with:

| Setting | Value |
|---------|--------|
| Repository | `amarnathepuru/mutual-fund-analyzer` |
| Branch | `main` |
| Main file | `app.py` |

After pushing to `main`, use **Manage app → Reboot app** so the cloud instance picks up the latest code.

**Python version:** set in the Cloud UI (Advanced settings), not in `packages.txt`. Do not put `python-3.11` in `packages.txt` — that file is only for Linux `apt` packages and will break the build.

If the public URL shows an old sidebar (“Analyze Category” / equity picker), that deployment is **not** this app — create a new app or fix the repo/branch/main file above. This codebase is **FundLens** (home → Analyse Portfolio → Portfolio X-Ray).

Data CSVs under `data/` are committed so the cloud app can load holdings without scraping.
