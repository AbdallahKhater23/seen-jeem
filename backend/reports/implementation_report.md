# Implementation Report — 12-Category Engine, Anti-Repeat Selector, Live Frontend

Date: 2026-10-20. Scope: the Seen Jeem backend + React frontend in this checkout.

## Status summary

| Area | Status |
| --- | --- |
| Schema v3, migrations, 12 categories | Implemented and tested |
| Three-layer selector, reservations, rerolls | Implemented and tested |
| Match lifecycle API (create/get/open/reveal/power/resolve/reroll/abandon/complete/adjust) | Implemented and tested |
| Curated + procedural content compiler | Implemented and tested |
| External harvester + sync job records | Implemented; network behaviour not exercised against live endpoints in this run |
| Live frontend cutover (lobby, board, arena, spotdiff) | Implemented; verified in a real browser against a seeded local API |
| 100 consecutive repeat-free matches | Proven on an isolated, clearly labelled capacity fixture |
| 100-match guarantee on the *real* bank | **Not achieved** — 30 of 36 buckets are below 201 eligible records |

## Measured results

| Check | Result |
| --- | --- |
| `python -m pytest` (backend) | 63 passed in 281.59 s |
| `node --test` (`backend/integration`) | 6 passed |
| `npm test` (`frontend`) | 114 passed / 15 files |
| `npm run build` (`frontend`) | success, 1976 modules, 497 kB JS |
| Cold offline seed | 5,152 inserted, 0 skipped, 0 invalid, 2.1 s |
| Seed origins | 1,792 curated, 3,360 generated puzzle |
| Content floor (120/bucket) | 29 buckets below |
| Capacity gate (201/bucket) | 30 buckets below |
| Football Arab share | 3.58 % (target 15 %) |
| Live browser run | match created, 6 categories, 36 tiles, spotdiff payload rendered, team1 win committed (score 200, version 2, `times_played = 1`) |

## Changed / added files

Backend:

- `app/schema.py` — schema v3, additive migrations v1→v2→v3.
- `app/db.py` — WAL/settings, `BEGIN IMMEDIATE` transaction helper.
- `app/models.py` — Pydantic contracts for categories, boards, draft, sessions, powers, resolve/reroll, sync.
- `app/api/routes/public.py` — 12-category catalogue with live eligibility, match lifecycle, powers, sync routes.
- `app/api/routes/admin.py`, `app/main.py` — admin surface and app wiring.
- `app/services/content.py` — fact→question compiler, validators, inventory report, difficulty rules.
- `app/services/selector.py` — casino shoe, usage filtering, fact cooldown/relaxation, allocation.
- `app/services/matches.py` — allocations, reservations, sessions, powers, reroll, resolve, abandon, completion, adjustments.
- `app/services/seed.py` — idempotent seeding, deck ordering, seed report.
- `app/services/harvester.py`, `app/services/sync.py` — RestCountries/Wikidata adapters, cache, cursor and job records, restart recovery.
- `app/data/*.py` — curated registries (countries, clubs, careers, UCL, World Cup, Arab football, records, general knowledge) and the deterministic spotdiff generator.
- `seed_data.py`, `seed_harvester.py` — CLIs.
- `tests/conftest.py`, `tests/test_schema_and_seed.py`, `tests/test_selector.py`, `tests/test_api_and_matches.py`, `tests/test_powers.py`, `tests/test_concurrency_and_recovery.py`, `tests/test_100_matches.py`, `tests/test_scoring.py`.
- `integration/frontendAdapter.js` and `integration/frontendAdapter.test.mjs` — contract mapping and tests.
- `README.md`, `reports/seed_report.json`, `reports/implementation_report.md`.

Frontend:

- `src/api/client.js`, `src/api/server.js` — live API client and adapter boundary.
- `src/store/gameStore.js` — server-authoritative match state, category catalogue, online resolve/reroll/adjust, recovery.
- `src/views/LobbyView.jsx` — live 12-category picker, exactly-six rule, random quick-pick, server match creation.
- `src/views/BoardView.jsx`, `src/views/ArenaView.jsx` — server tiles/questions, category names from the live catalogue, resolve flow.
- `src/components/SpotDifferenceRenderer.jsx` — backend anchors/mutations/differences; each declared difference is a real interactive target; exactly three differences rendered.
- `src/components/Icon.jsx`, `src/ui/categoryArt.js`, `src/game/state.js` — icon and category support for the wider catalogue.
- Tests: `src/api/client.test.js`, `src/store/categorySelection.test.js`, `src/store/gameStore.server.test.js` (updated), `src/components/SpotDifferenceRenderer.test.jsx`.

## Verification details

- `tests/test_100_matches.py` creates and resolves 100 consecutive matches on the capacity fixture: 3,600 resolved tile results, 3,600 unique question IDs, 54 distinct IDs and 54 distinct fact groups per allocation, `times_played` equal to played tiles only, zero questions with `times_played > 1`.
- `test_production_capacity_shortfall_is_documented` fails the build if the real bank is ever reported as meeting the 100-match gate without the underlying rows.
- Live browser verification used a temp database (`backend/data/live_check.db`, git-ignored) seeded with the offline CLI. The served API returned the 12 real categories; the board showed six category pods with Arabic server names; opening `spotdiff-200-1` rendered the scene declared in `payload`, revealing showed the three backend difference labels, and the committed win persisted to SQLite.

## Blockers and risks

1. **Content capacity.** 30 buckets are below 201 eligible records; 29 are below the 120 floor. A universal 100-match guarantee cannot be claimed until verified content grows. No rows were fabricated to close the gap.
2. **Football distribution.** 3.58 % Arab vs 15 % target; the ratio is measured from explicit scope tags.
3. **External sources.** The harvester is implemented with cache, validation, timeouts, and non-fatal failure handling, but this run did not perform a live network harvest, so no API-yield claim is made. Wikidata rows are stored for review, not auto-published as questions.
4. **Sync durability.** Jobs run via FastAPI `BackgroundTasks`; they are recorded and marked failed after restart, and the API reports `durable: false`.
5. **Flaky diagnosis note.** A pytest run before clearing `__pycache__` executed stale bytecode and reported two schema assertions against version 2. After removing caches, the full suite passed against schema v3. No test was weakened.

## Reproduction

From `backend/`:

```bash
./.venv/Scripts/python.exe -X utf8 seed_data.py
./.venv/Scripts/python.exe -m pytest
cd integration && node --test
```

From `frontend/`:

```bash
npm test
npm run build
VITE_API_PROXY=http://127.0.0.1:8000 npm run dev
```

Serve the API with `DATABASE_PATH=data/seenjeem.db ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
