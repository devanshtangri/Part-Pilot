# Chat 22 Patch 646 diagnostic — MCP permission transform recovery

## Status

Patches 644 and 645 were both consumed by consecutive pre-write source
transformation failures. Neither patch wrote application source, built an image,
migrated SQLite, deployed, staged, committed or pushed.

The authoritative application baseline remains the Patch 643 diagnostic commit:

- HEAD/origin: `7786850ba0d40579a4b6dd1db0d3d9e4f82c0f45`
- subject: `Diagnose MCP tool permissions`
- deployment:
  `sha256:45484acf35311d5efee4f9c38c19d6edbadca137cc0f7b0039110b2ebf50458b`
  healthy, restart count 0
- Alembic: `0015_mcp_direct_clients (head)`
- Git/index: clean

Patch 646 is diagnostic-only. It writes, stages, commits and pushes only this
`docs/diagonostic_*.md` report.

## Failure evidence

### Patch 644

- script SHA-256:
  `e4cf284eb1cc6ef6ffa5e0c0196650d5479c415195463a5b6f1ef4e0a469c325`
- log SHA-256:
  `2040c308958f220db1d467a045048ab400bee15542df1a943b9733125e38081a`
- terminal failure:
  `search_parts authorization anchor count mismatch: expected 1, found 2`
- failure occurred during in-memory source transformation before writes.

Root cause: `backend/app/mcp/part_tools.py` contains two identical
`_ensure_read_tools_enabled(db)` call lines globally, one in each registered
inventory tool. A global exact-one replacement was invalid.

### Patch 645

- script SHA-256:
  `97f131af3d8a347c2e272b820708fa25fc7330ad3c4c47942c48a0688fe7bff2`
- log SHA-256:
  `79dd7e624eb438a06bd40c79601b951ea69893391dbf64a9f63467b258eebce1`
- terminal failure:
  `list_projects authorization anchor count mismatch: expected 1, found 4`
- failure occurred during in-memory source transformation before writes.

Root cause: `backend/app/mcp/workspace_tools.py` contains four identical
`_ensure_read_tools_enabled(db)` call lines globally, exactly one in each
registered workspace tool. Patch 645 fixed Part-tool scoping but repeated the
same global-exact-one mistake for workspace tools.

## Exact current source fingerprints

- `backend/app/mcp/part_tools.py`
  `3630f50532f0a2a77fe5f06571d20283afd8879c4cabd661ffbb9a4a8fa581fa`
- `backend/app/mcp/workspace_tools.py`
  `e0e9916ca8345a1e822fe63650ce84648d6fbc30a0b71156eeff1538c1c942a6`
- `backend/app/mcp/runtime.py`
  `07835598a918ad6e7527fcb53dd523b9be9ec485bca14dc05ecaf4ce3b97b6e0`
- `backend/app/models/core.py`
  `ff93a4ac6466562cd41db734d4c0e9977b9a6566b5cf41da4714f354c9ebd7d6`
- `backend/app/services/backups.py`
  `9e8d68da13b2e1e79c8d595318962ad1c2e5c3f281ce9f9dae2dcfb602b2c6a9`
- `backend/app/db/mcp_workspace_tools_smoke_test.py`
  `9300d5f1b088648164485bd8860d9011cad507d6510651dd974eb5101b1f0380`
- `backend/app/db/mcp_oauth_smoke_test.py`
  `725e90103ccc953aed90db4f29ab4ca8d159f09cdabb08617feb6bae6587e823`
- `backend/app/db/backup_smoke_test.py`
  `ce152e6668f4fb769ef84fa5476a0f3aeb6a598115814215a3a19b5e7c6cf05a`
- `backend/app/db/seed.py`
  `6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de`
- `backend/app/db/smoke_test.py`
  `881c409fb4f0f796b406d645edafb21b444a3cf183fc5f67c278d1b16c697412`
- Patch 643 architecture report
  `a217f1654c09354d41f576f6a1238b850433203883928a8f69887109bddbf437`

The intended Patch 647 additive files are still absent:

- `backend/alembic/versions/0016_mcp_tool_permissions.py`
- `backend/app/services/mcp_permissions.py`
- `backend/app/db/mcp_tool_permissions_smoke_test.py`

## Discovered Part-tool block shapes

`part_tools.py` has exactly two coarse-guard calls:

- `search_parts()` — one call inside its `try` block.
- `get_part_details()` — one call inside its `try` block.

The old `_ensure_read_tools_enabled()` helper is a separate top-level function
before `_validate_search_arguments()`.

Safe transformation:

1. replace the single import
   `MCP_SCOPE_READ, available_scopes` with `MCP_SCOPE_READ` plus
   `authorize_mcp_tool`;
2. remove `_ensure_read_tools_enabled()` using the verified source-index range
   from its function start through the two-newline boundary immediately before
   `_validate_search_arguments()`;
3. isolate the `search_parts()` function from its `def` through the decorator
   that starts `get_part_details()`, and replace exactly one guard inside that
   block;
4. isolate `get_part_details()` from its `def` to EOF and replace exactly one
   guard inside that block.

Read-only rehearsal result:

`backend/app/mcp/part_tools.py`
→ `e42ccb83c314d6553ed424090ea38fea64033341166e617102452522546aff38`

This exactly matches the previously successful isolated backend candidate.

A literal helper-block deletion was separately tested and produced a different
SHA, proving that helper removal must use the verified structural boundary
rather than whitespace reconstruction.

## Discovered workspace-tool block shapes

`workspace_tools.py` has exactly four coarse-guard calls globally and exactly
one inside each named registered tool:

- `list_projects()` — one.
- `get_project_details()` — one.
- `list_reservations()` — one.
- `get_reservation_details()` — one.

Safe transformation:

1. remove the single `_ensure_read_tools_enabled` import;
2. add the single `authorize_mcp_tool` import;
3. for each registered tool, isolate the function body using its `def` start and
   the following tool decorator boundary;
4. replace exactly one guard inside that isolated function block with the
   matching canonical tool name.

Read-only rehearsal result:

`backend/app/mcp/workspace_tools.py`
→ `6e418c7e923f548068e32e482acb2082647db2fb873d3d13615e73115db17e37`

This exactly matches the previously successful isolated backend candidate.

## Rehearsed backend contract retained

The previously isolated backend candidate remains the target for Patch 647:

- Alembic `0016_mcp_tool_permissions`;
- global `mcp.tool_permissions`;
- `denied_tools_json` on OAuth and named-direct clients;
- all six current read tools enabled by compatibility default;
- global policy as a hard ceiling;
- OAuth/direct clients may deny individual tools;
- no-auth inherits global policy only;
- tool-specific guard executes before business-data access;
- existing failed `mcp.tool_called` audit path records denied calls;
- no MCP write tools are introduced.

The previously rehearsed strict schema fingerprints remain:

- `0015`: `4c4017e84da3725adc5c20060e0452ad37aded19493b1c9b2a46e7c714f7f339`
- `0016`: `ee430d771826a549316a354a9c307198e12b9e473be28ced5a38f13ba3796d6d`

The isolated migration already proved:

`0015 → 0016 → exact 0015 → exact 0016`.

## Patch 647 implementation requirements

Patch 647 may resume the backend/schema foundation only after this diagnostic is
committed/pushed and re-read.

It must:

1. preflight the exact Patch 646 report commit and clean Git/index;
2. pin Patch 644/645 failure evidence;
3. compute all candidate transforms entirely in memory before backup/write;
4. use the verified function-scoped Part/workspace transformations described
   above;
5. validate every resulting candidate SHA before the first write;
6. preserve the previously rehearsed twelve-file backend candidate contract;
7. compile Python and run `git diff --check`;
8. canonical Docker build;
9. on a copied database:
   - upgrade to `0016`;
   - run MCP permission smoke;
   - run workspace invocation-denial/audit smoke;
   - run OAuth schema smoke;
   - run named-direct-client smoke;
   - run backup smoke;
   - run complete Part Pilot smoke;
   - verify exact `0015 ↔ 0016` schema reversibility;
10. only after isolated checks pass, backup/migrate live SQLite and deploy;
11. verify existing OAuth/direct clients inherit all six tools and the new
    global policy enables all six;
12. prove pre-existing application/security data, credentials, instance secret,
    restore staging and inventory are preserved;
13. leave backend source uncommitted for the next API/client-semantics slice.

Patch 647 must not start the Settings UI or MCP write-tool work.

## Why implementation is safe to resume after Patch 646

There is no pending application source and no ambiguity about local source.
Both failed implementations stopped before writes. The exact problematic block
shapes are now known, and the structural transforms for both MCP tool modules
have been rehearsed read-only to the same hashes as the already-tested backend
candidate.
