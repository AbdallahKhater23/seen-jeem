# SEEN JEEM Expansion — Final Evidence Report

Generated: 2026-10-21 (local)  
Repository: `C:\Users\pc\Downloads\seen jeem`  
Schema: `7`  
Live database: `backend/data/seenjeem.db`

## 1. Outcome

The five requested categories were implemented, seeded, migrated, and tested:

| Category | Arabic name | Icon | New questions | Buckets (200/400/600) |
|---|---|---:|---:|---:|
| `quran` | القرآن الكريم | `BookOpen` | 360 | 120 / 120 / 120 |
| `nicknames` | ألقاب اللاعبين | `Tag` | 360 | 120 / 120 / 120 |
| `technology` | معلومات تقنية | `Cpu` | 360 | 120 / 120 / 120 |
| `videogames` | ألعاب الفيديو | `Gamepad2` | 360 | 120 / 120 / 120 |
| `matchstick` | ألغاز أعواد الثقاب | `Activity` | 360 | 120 / 120 / 120 |

- New questions: **1,800** (15 buckets × 120).
- New-bucket shortfall: **0**.
- Bank total: **6,952** questions across **17 categories / 51 buckets**.
- Live DB total after additive seed: **8,227** questions.
- Existing 6,427 questions, 6,427 fingerprints, and 6 matches were preserved.
- The second seed inserted **0** rows and skipped **6,952**; counts were unchanged.

## 2. Content and provenance

Offline deterministic snapshots are stored in `backend/app/data/snapshots/`. Seeding does not require network access.

| Category | Source | Snapshot | Selection |
|---|---|---|---|
| Quran | AlQuran Cloud API metadata; Quran text attribution Tanzil.net | `quran_surahs.json` | 114 surahs × 3 + 18 referenced general facts |
| Nicknames | Wikidata `P1449` nickname, `P27` country, `P413` position | `football_nicknames.json` | 360 players, 120 per tier |
| Technology | Wikidata `P17` country, `P112` founder, `P571` inception | `technology_companies.json` | 155 filtered companies; 120 with Arabic labels |
| Videogames | Wikidata `P178` developer, `P123` publisher, `P577` release, `P400` platform | `videogames.json` | 130 eligible; 120 with Arabic titles |
| Matchstick | Internal deterministic generator | `shared/matchstick_segments.json` | 360 generated puzzles |

Every new question carries:

- `source_name`
- `source_url` (HTTP for API rows; `internal://seenjeem/matchstick-generator/v1` for procedural puzzles)
- `source_entity_id`
- `source_claim`
- `source_checked_at` (`2026-10-20`)
- `source_license`
- deterministic `fingerprint`

API rows use CC0 1.0 for Wikidata and the documented AlQuran Cloud/Tanzil attribution for Quran metadata. Procedural rows use `internal deterministic generator` with an explicit uniqueness/segment-conservation claim.

The legacy 6,427 rows retain their original content and fingerprints. Their new `source_license` / `source_claim` columns remain `NULL` because their original license is unknown; no license was invented for them.

## 3. Matchstick engine and renderer

- Generator/validator: `backend/app/data/matchstick.py`.
- Shared geometry: `shared/matchstick_segments.json` (read by both Python and React).
- Payload kind: `payload.kind = "matchstick"`.
- DB storage: existing `question_type = "text"` plus the typed payload; the frontend adapter promotes it to the dedicated frontend type `matchstick`. This preserves the existing SQLite `CHECK` constraint and avoids a destructive table rebuild.
- Renderer: `frontend/src/components/MatchstickRenderer.jsx`; routed from `ArenaView.jsx`.
- Animation: moves from source to destination in global SVG coordinates, highlights moved sticks, and reveals the solution.
- Difficulty rule: 200/400 require exactly one move; 600 requires exactly two.
- Strict validation: **360 / 360 passed**; **0 failures**; **360 unique equations**; **0 segment-conservation failures**.
- Cross-column moves: 123; covered by a renderer regression test after fixing a source-column offset bug.

## 4. Schema, migration, and seeding

- `SCHEMA_VERSION = 7`.
- Additive migration adds nullable `source_license` and `source_claim` to `questions` and `fact_records`.
- No table truncation, no reset, no deletion.
- Live pre-seed state: version 6, 12 categories, 6,427 questions, 570 facts, 6 matches, 6,427 fingerprints.
- Migration-copy result: version 7, same 6,427 questions / 6 matches / 6,427 fingerprints, columns added, no categories added before seeding.
- Populated-copy seed: inserted 1,800, skipped 5,152, invalid 0; second run inserted 0, skipped 6,952; counts identical.
- Live seed: inserted 1,800, skipped 5,152, invalid 0; second run inserted 0, skipped 6,952.
- Live final state: version 7, 17 categories, 8,227 questions, 4,302 fact records, 6 matches, 8,227 distinct fingerprints, `integrity_check = ok`, zero foreign-key violations.
- Backups:
  - `backend/data/backups/seenjeem-before-v7-20261020T210149Z.db`
  - `backend/data/backups/seenjeem-before-matchstick-provenance-20261020T212752Z.db`

## 5. Verification executed

### Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
```

Result: **97 tests passed**, exit code 0.  
Includes existing six-category lobby, 100-match anti-repeat, transactional resolution, concurrency, accounts, admin, schema, and the new expansion tests.

New tests: `backend/tests/test_seenjeem_expansion.py` (5 tests) cover:

- exact 120-per-bucket counts for all 15 new buckets;
- strict uniqueness and segment conservation for all 360 matchstick puzzles;
- complete provenance for all 1,800 new rows;
- v6→v7 migration preserving rows, matches, and columns;
- idempotent reseeding with all new categories;
- live API serialization of matchstick payload and provenance.

### Frontend

```powershell
cd frontend
npm test
npm run build
```

Result: **140 tests passed in 21 files**, exit code 0.  
Production build: **success**, exit code 0, 1,987 modules transformed, main bundle 376.32 kB (110.29 kB gzip).

New frontend tests:

- `frontend/src/api/frontendAdapter.test.js`: new category mapping, `payload.kind=matchstick` → frontend `matchstick`, provenance passthrough.
- `frontend/src/components/MatchstickRenderer.test.jsx`: SVG stick count, solution reveal, two-move caption, safe fallback, and cross-column destination coordinates.

### Live API

Verified against `backend/data/seenjeem.db` through the ASGI app:

- `/api/v1/health`: status `ok`, schema `7`, categories `17`, active `8,221`.
- `/api/v1/categories`: 17 rows; the five new icons are exactly `BookOpen`, `Tag`, `Cpu`, `Gamepad2`, `Activity`; each new category reports 360 eligible questions.
- `/api/v1/questions/{id}`: every new category returned complete provenance; matchstick returned `payload.kind = "matchstick"` and the internal generator URI/date.

### Generated report

- `backend/data/reports/seenjeem-expansion-report.json`
- `backend/data/reports/seenjeem-expansion-report.md`

## 6. Existing shortfalls (not inflated)

The five new categories have zero shortfall. The following **29 pre-existing buckets** remain below the 120 content floor and were deliberately not padded with fabricated data:

```text
flags       200=100  400=100  600=100
capitals    200=100  400=100  600=100
football    200=13   400=19   600=10
ucl         200=69   400≥120  600=69
worldcup    200=56   400=56   600=56
career      200=100  400=100  600=82
clubs       200=100  400=100  600=100
arab_ftbl   200=9    400=13   600=19
numbers     200=9    400=11   600=16
general     200=18   400=20   600=9
```

These are reported in `buckets_below_content_floor` in the generated JSON. No existing row was deleted or rewritten to improve the count.

## 7. Blocked or limited

1. **No Git repository**: the workspace has no `.git`; commit/diff evidence cannot be produced.
2. **IGDB unavailable**: it returns HTTP 401 without credentials. Videogames use the cited Wikidata snapshot instead.
3. **Legacy provenance**: 6,427 pre-existing question rows have `NULL` license/claim because their original license is unknown. They were preserved verbatim.
4. **Independent cross-verification**: new facts are verified against the cited source snapshots, not against a second independent source. This is documented per row via source name/URL/entity/claim/date.
5. **Browser-level animation**: the renderer is SSR-render tested and production-built; a real-browser screenshot/frame-by-frame visual check was not run because no browser automation is available in this environment.
6. **Data quality caveats**: nickname tier 600 includes some obscure players; videogame developer/publisher names are proper nouns and may be Latin-script even when the game title is Arabic.

## 8. Key files

- `backend/app/services/content.py` — 17-category registry, validation, inventory.
- `backend/app/data/matchstick.py` — deterministic generator, solver, strict validator.
- `backend/app/data/quran.py`, `technology.py`, `videogames.py`, `nicknames.py` — row generators.
- `backend/app/data/snapshots/` — offline source snapshots.
- `backend/app/schema.py`, `backend/app/db.py` — schema v7 and additive migration.
- `backend/app/services/seed.py` — idempotent seeding and provenance persistence.
- `backend/integration/frontendAdapter.js` — category/type/payload mapping.
- `frontend/src/components/MatchstickRenderer.jsx` — animated SVG renderer.
- `frontend/src/views/ArenaView.jsx` — renderer routing.
- `frontend/src/components/Icon.jsx`, `frontend/src/ui/categoryArt.js` — icons/art mappings.
- `backend/scripts/harvest_fact_snapshots.py` — snapshot harvester.
- `backend/scripts/report_expansion.py` — repeatable report generator.
