# Account system verification

Journeys derived from the request: create an account, return with the same account,
and avoid previously encountered questions across matches and browsers.

## Implemented guarantees

- Registration/login/logout with salted scrypt passwords, hashed revocable session
  tokens, HttpOnly cookies, expiry, CSRF checks, and throttled authentication attempts.
- The signed-in account is attached by the server to each frontend-created match.
  Supplying another account's participant ID cannot impersonate it.
- Opening or replacing a visible question records account history. Selection uses
  that history across browsers and deck cycles; exhaustion returns a conflict.
- Separate accounts on a shared browser do not inherit device-shadow history.
- Existing databases, question history, and guest profiles survive additive migration.
- Arabic account screen, question counter/history, and account-aware local recovery.

## Evidence

| Check | Observed result |
| --- | --- |
| Backend RED: `pytest tests/test_accounts.py --maxfail=1` | Account registration returned 404 before implementation. The sandbox temp-folder error was resolved before recording RED. |
| Frontend RED: `npm test -- --run src/components/AccountGate.test.jsx` | Intended missing `AccountGate.jsx` import failure. |
| Backend account + identity tests | Passed after implementation. |
| `pytest tests/test_accounts.py tests/test_schema_and_seed.py tests/test_api_and_matches.py` | Passed after updating the obsolete schema-version assertion. |
| Final account-binding/expired-cookie regression | 1 passed, 88.20 seconds. |
| Final duplicate-name/password/CSRF regression | 1 passed, 69.96 seconds. |
| `npm test` | 132 tests passed in 19 files. |
| `node --test` in `backend/integration` | 7 passed. Updated the expected metadata shape to accommodate concurrent source-license changes. |
| `npm run build` | Succeeded after final account changes. |
| Live HTTP | Frontend and account module returned 200; proxied backend health reports ready; all five account routes appear in OpenAPI. |

The initial full backend run had one obsolete schema-version assertion failure;
the affected suite passed on rerun. Category/source-metadata work changed concurrently
in this folder; the final focused backend tests and frontend build used those changes.

Before applying the account migration, a SQLite backup was saved as
`data/seenjeem-before-accounts-20261020-231921.db`.

## Review and limits

Reviewed server-derived identity binding, hashed storage, session revocation/expiry,
CSRF handling, parameterized queries, account switching, and stale history responses.
Automated browser surfaces were unavailable; React DOM interaction tests and live HTTP
checks ran, but a visual browser pass was not completed. Coverage tooling was not
installed, so no percentage coverage is claimed. This checkout has no Git repository;
there are no checkpoint commits.

Accounts work against this backend's SQLite database; they are not an external cloud
identity service. Password recovery and email verification are not implemented.

## Self-evaluation

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 4/5 | Account and persistence tests pass; no visual browser evidence. |
| Completeness | 4/5 | Requested login/history/no-repeat behavior implemented; hardware multi-device testing was simulated with separate HTTP clients. |
| Clarity | 4/5 | Arabic UI distinguishes accounts from guest profiles; existing lobby still has a separate guest section. |
| Actionability | 5/5 | Running at `http://127.0.0.1:5174`, ready for signup. |
| Conciseness | 4/5 | Reuses existing history/selection; account UI also includes pagination and error handling. |

Overall: 4.2/5. Next useful checks: a visual browser pass and deployment-level HTTPS
cookie verification. The reported limits match the evidence available to the user.
