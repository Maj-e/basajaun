# Contract fixtures

Used by `scripts/tests/test_contract_fixtures.py` (runs in CI as "Contract self-test").

- `valid/` — one correct example of each contract file (hotspots in Chile, Canada and Australia: the contract is world-wide). Every file **must pass** `validate.py`.
- `invalid/<case>/` — one deliberately broken file per folder, named after what is broken. Every file **must fail**.

When the contract changes (`docs/data_contract.md` + `docs/schemas/`), update `valid/` first; when a new rule is added, add an `invalid/` case for it.

Run locally: `make contract-test`.
