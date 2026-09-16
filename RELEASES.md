# Releases

## 2026-09-15 — First deploy
- **What deployed:** https://ledeline.levelbrook.com (Cloudflare Pages project `ledeline`, custom domain via the Pages domains API, DNS CNAME proxied). Static report of run `results/run-2026-09-15.json`.
- **Changed:** initial release: spec-driven workflow, deterministic checks (10 tests), Gemini judge, model x story runner with per-story ship gate, static report. Corpus: ten HN front-page articles from 2026-09-15 with hand-written must-mention notes.
- **How:** `python3 -m ledeline.report results/run-2026-09-15.json site/index.html && CLOUDFLARE_API_TOKEN=$LEVELBROOK_CF_DEPLOY_TOKEN CLOUDFLARE_ACCOUNT_ID=a67eceeb4b89d2d4171ed209e87c9456 npx wrangler pages deploy site --project-name=ledeline --branch=main --commit-dirty=true`
- **Verified:** HTTP 200 on the custom domain, page title and "DOES NOT SHIP" gate verdict present, screenshot reviewed; repo public at github.com/tachyurgy/ledeline (200).
