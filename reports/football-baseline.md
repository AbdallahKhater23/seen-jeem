# Football bank baseline and verified editorial pilot

Captured 2026-10-21 from `backend/data/seenjeem.db` using SQLite URI `mode=ro`. No migration, seeding, match creation or history write was performed by the audit. Full reproducible results and schema are in `football-baseline.json`; its active football row snapshot SHA-256 is `0f1858a9e59b9d50648ca194bf6db611fbb7cec4453346052d5f97092563d2ed`.

## Deterministic baseline

| Category | Active | 200 | 400 | 600 | Distinct legacy groups | Missing source URLs |
|---|---:|---:|---:|---:|---:|---:|
| football | 343 | 114 | 119 | 110 | 343 | 343 |
| ucl | 276 | 69 | 138 | 69 | 69 | 276 |
| worldcup | 301 | 100 | 101 | 100 | 301 | 301 |
| career | 483 | 200 | 101 | 182 | 401 | 483 |
| clubs | 300 | 100 | 100 | 100 | 100 | 300 |
| arab_ftbl | 41 | 9 | 13 | 19 | 27 | 41 |
| numbers | 36 | 9 | 11 | 16 | 28 | 36 |
| nicknames | 360 | 120 | 120 | 120 | 360 | 0 |
| **Total** | **2,140** | **721** | **703** | **716** | — | **1,780** |

Legacy groups are **not canonical facts**. Some represent an event, club or player, so a group collision is not proof of a factual duplicate. Likewise shared answers are not duplicate facts. Normalized question text has zero excess rows outside careers; careers have 204 excess rows (42.24%). Career text often has different structured clues in its payload, so this is repeated presentation text rather than proof that 204 full questions are duplicates.

There were no foreign-key violations at baseline. SQLite `user_version` was 7. Existing question types are constrained to flag/text/career/spot_diff. Metadata such as canonical era, archetype, mechanic and fact identity did not exist in that schema, so their actual distributions cannot be retrospectively measured as verified facts.

## Why the game feels repetitive

`backend/app/services/content.py::_ucl_rows` creates four rows per final: winner, runner-up, city and stadium. The actual data has exactly 69 rows beginning with each of those four templates. `_clubs_rows` creates city, league and country questions: all 300 club rows belong to those three template families (100 each). General football also contains 100 rows in each of those three families: 300/343 are club geography/league questions.

`_worldcup_rows` generates repeated tournament-year views including host, winner, runner-up, final result, venue and third place. The stored World Cup bank has repeated prefixes in blocks of 22. Many are different facts but very similar experiences. `_career_rows` repeatedly derives clues from the same careers. Five answer appearances each for Messi, Cristiano Ronaldo, Neymar, Mbappe, Benzema, Salah and several other stars are visible in the actual bank.

`backend/app/data/snapshots/football_nicknames.json` describes Wikidata P1449 extraction. The active bank has 120 prompts beginning “ما اللقب الذي يعرف” and 120 beginning “من اللاعب الذي يلقب”. A spot-check includes “Boquita”, “Empachi”, “Kalaba”, “Ronaldo van de armen” and “Papá de Perú”. These entries need local audience recognition and ambiguity review; the audit does not declare them false merely because they are unfamiliar. `verified_api` records successful ingestion, not editorial suitability.

The baseline therefore exhibits **template repetition despite text uniqueness**. Existing group IDs also mix entity identity with event identity. Production source provenance is absent from 83.18% of the active football rows (1,780/2,140), preventing the audit from independently establishing their truth from stored evidence.

## Explicitly heuristic findings

The audit masks digits and counts the first four normalized words as a template estimate. It does not use embeddings. This catches clear generation families but can split similar templates or combine unrelated ones.

Era estimates use an unambiguous explicit year in question wording, otherwise `unknown`. UCL gives classic 136, golden 64, modern 52 and contemporary 24. World Cup gives classic 160, golden 49, modern 52, contemporary 19 and unknown 21. These are wording-based estimates, not verified event-era backfills. Career and club histories without explicit years are deliberately unknown. The audit cannot defensibly assign primary subjects or event clusters to all legacy rows automatically.

Ambiguity, factual invalidity, source accessibility, external media validity and perceived enjoyment are **not exhaustively measured**. A URL's presence is provenance coverage, not proof that the URL supports the answer. No before/after enjoyment percentage is claimed.

## Source-verified Gulf Arabic pilot

`backend/app/data/football_curated.py` supplies 121 original questions: 15 per category, five at each difficulty, plus one supplemental Champions League 600 lineup question, with 121 distinct canonical fact IDs. Five initial cross-category fact variants were replaced with independently verified facts after the returning-player simulation exposed insufficient remaining content. There are ten `career_tree` payloads, one `odd_one_out_grid` and one `lineup_svg`. Every prompt is at most 96 characters in the direct import check. Every row has a specific official-source claim and inspected URL; 79 unique official pages are referenced.

The lineup shows Liverpool’s eleven verified starters from the official UEFA 2005 final record, with Harry Kewell hidden. Its title explicitly says the positions are illustrative and its formation label is “توزيع توضيحي”. No precise historical formation, coordinates or jersey numbers are claimed. Direct visual validation checked eleven distinct players and exactly one hidden marker; public projection omitted the hidden name, while authorized revealed projection restored it. Parent integration owns checking complete question-payload secrecy through the API.

The source manifest uses FIFA, UEFA, AFC, CAF, Premier League and official club archives. Public factual sources do not confer rights to their media. The pilot contains original wording, structured text labels, and no copied images, badges or video. Search-index article bodies were used when FIFA's directly opened page returned no extracted text; this limitation is disclosed rather than claiming inaccessible pages were fully viewed.

Editorial choices: questions use Gulf wording such as منو، شنو، خذ، هالمنتخب، دقايق. Career graphics explicitly say “محطات مختارة بالترتيب”; they do not claim complete careers, fees or exact years. Multi-era subjects remain unknown. Changing records are avoided by edition/year-specific wording. Alias lists avoid bare “Ronaldo” for the two ambiguous footballers. Historical scores and numbers use exact tolerance.

## Coverage and limitations by category

| Category | Improvement | Remaining limitation |
|---|---|---|
| General football | Upsets, tournament substitutions, penalty technique, managers, odd-one-out | European national-team stories still dominate this pilot |
| Champions League | Iconic goals, late equaliser, clever corner, substitutes, shoot-out save | Liverpool/Real Madrid concentration remains; soft event penalties cannot create missing content |
| World Cup | Celebrations, African success, late drama, classic upset | Several Ghana–Uruguay facts need separation across rounds |
| Careers | Original selected-stop diagrams, transfers, forgotten loans and connections | Ten graphics plus textual clues; no fully dated complete careers |
| Clubs | Rivalries, supporter culture, managers, underdogs and famous goals | European focus; no global-club claim |
| Arab football | Saudi, Iraqi, Qatari, Moroccan, Algerian, Kuwaiti and Egyptian moments | Kuwait 1980 and Egypt 2010 now verified; broader club and regional coverage still needed |
| Numbers | Historically bounded, recognizable achievements and a deduction | Some precise totals may feel less entertaining; difficulty remains editorial |
| Nicknames | Recognizable contextual nicknames, reversed and clue-based forms | Predominantly player and club nicknames; only one archetype is appropriate |

Quality and difficulty confidence values are declared editorial estimates. No human playtest has established entertainment or answer rates. Five candidates per tier provide two rounds' visible questions plus one reserve when only the two played questions per tier become permanent history and unused reserves are released. Actual capacity also depends on cross-category facts, participant history unions and concurrent reservations; the parent's repeated-session simulations determine that outcome. This is still a small pilot, not a high-capacity replay bank. Safe typed exhaustion is preferable to reusing seen content.

## Reproduction and verification

Reproduce with `backend/.venv/Scripts/python.exe backend/scripts/audit_football.py --database backend/data/seenjeem.db --output reports/new-audit.json` from the project root. The database connection is always read-only; only the explicitly selected report path is written. Running the audit is optional and is not wired into startup, Git or agent hooks.

Executed directly: Python imports of the audit and curated data, active database read-only queries, full count/difficulty/fact/source/visual/length checks. Parent implementation owns integration, migration, selection, UI tests and gameplay simulations; this report does not claim those passed before their actual execution.
