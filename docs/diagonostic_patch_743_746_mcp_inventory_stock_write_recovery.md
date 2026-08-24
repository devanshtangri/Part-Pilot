# Diagnostic: Patch 743-745 MCP inventory stock-write recovery

<!-- PARTPILOT:MCP_INVENTORY_STOCK_WRITE_RECOVERY_DIAGNOSTIC:V746 -->

## Scope

Patch 746 is diagnostic-only. It follows the Patch 743/744 recovery failures and consumed Patch 745 syntax failure: Patch 743 stopped while validating generated Markdown, and Patch 744 stopped in preflight because its recovery predicate required console-only failure-summary text to exist inside the Patch 743 tool log.

Patch 746 does not modify application source, production SQLite data, Alembic state, runtime image, or deployment. It records exact script/log hashes, exact local Git/index/runtime/database state, verified source block shapes, anchor counts, and a safe implementation plan.

## Authoritative baseline before diagnostic commit

- HEAD: `d79c7e5f1f66cef73ade6c5309ce41516f8c07b0`
- origin/main: `d79c7e5f1f66cef73ade6c5309ce41516f8c07b0`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Git/index: clean
- Runtime: `image=sha256:e5d90cbdc5dc376a4b8b6ab5ff61c39fd0ed381886c51f8d1707d43f1c2c8559 health=healthy restart=0`
- Production Alembic: `0018_mcp_write_intents`
- Production SQLite: `PRAGMA quick_check=ok`, no foreign-key violations
- MCP permission key set: `search_parts`, `get_part_details`, `list_projects`, `get_project_details`, `list_reservations`, `get_reservation_details`, `reserve_project`, `consume_reservation`, `cancel_reservation`
- MCP permission values remain mutable and are deliberately not recorded or frozen.

## Exact consumed-patch and tool-log evidence

- `fixes/743_diagnose_mcp_inventory_stock_write_anchors.py` — `7998bb6d258a2da416cac27473596dbcf7aabd3580fc8b7aa5e51669b17dc830`
- `fixes/744_recover_mcp_inventory_stock_write_anchor_diagnostic.py` — `938eff52e1c1be324213b2f5484a250dfb516eab39e2283f571de8d488fd54ad`
- `fixes/logs/743_mcp_inventory_stock_write_anchor_diagnostic_20260824-094556.log` — `9f60c4befa480b5f05b94d3f115076cb26e20d5ad9be46186a1571216e7dc82a`
- `fixes/logs/743_mcp_inventory_stock_write_anchor_diagnostic_20260824-094806.log` — `382b857e1f2487420619f7dbe570ad68dae0cd045731ecdd710373e7de5e6274`
- `fixes/745_diagnose_mcp_inventory_stock_write_recovery.py` — `b89fb742099c06212bb4834dc97a5435fa16543beab9c064621cf7f8d3fb5a6b`

### Patch 743 tool log

```text
[1/5] Validating exact clean Chat 25 boundary Git/index, committed application bytes, healthy runtime, 0018 database and dynamic nine-key MCP policy shape
$ git branch --show-current
rc=0
main
$ git remote get-url origin
rc=0
git@github.com:devanshtangri/Part-Pilot.git
$ git fetch origin main
rc=0
From github.com:devanshtangri/Part-Pilot
 * branch            main       -> FETCH_HEAD
$ git rev-parse HEAD
rc=0
d79c7e5f1f66cef73ade6c5309ce41516f8c07b0
$ git rev-parse origin/main
rc=0
d79c7e5f1f66cef73ade6c5309ce41516f8c07b0
$ git log -1 --pretty=%s
rc=0
Checkpoint safeguarded MCP writes and complete Chat 25
$ git status --porcelain=v1 --untracked-files=all
rc=0
$ git diff --cached --name-only
rc=0
$ docker inspect -f 'image={{.Image}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restart={{.RestartCount}}' partpilot
rc=0
image=sha256:e5d90cbdc5dc376a4b8b6ab5ff61c39fd0ed381886c51f8d1707d43f1c2c8559 health=healthy restart=0
[2/5] Inspecting exact inventory quantity-service, audit-attribution, guarded-write, permission, migration, seed and workspace-registry source shapes after two isolated anchor mismatches
[3/5] Building docs/diagonostic_patch_743_mcp_inventory_stock_write_anchors.md with exact excerpts, anchor counts and the bounded Patch 744 implementation plan
[4/5] Proving application bytes/index/runtime/database remain unchanged, staging only the diagnostic report, then committing and pushing documentation-only evidence
```

The log reaches phase `[4/5]`, contains no `[5/5]`, no `Everything PASS`, and no `git add`, `git commit`, or `git push` command. The diagnostic report is absent after rollback and Git/index remain clean.

### Patch 744 impossible evidence predicate

Patch 744 reads the Patch 743 tool log and requires the following source shape:

```text
209:     require(PATCH743.is_file(), "Consumed Patch 743 script is missing", phase)
210:     require(
211:         sha(PATCH743) == PATCH743_SHA256,
212:         "Consumed Patch 743 script fingerprint changed",
213:         phase,
214:     )
215:     require(PATCH743_LOG.is_file(), "Patch 743 failure log is missing", phase)
216:     patch743_failure = PATCH743_LOG.read_text(encoding="utf-8", errors="replace")
217:     required_failure_lines = (
218:         "Patch 743 failed.",
219:         "Phase: diagnostic report write",
220:         "Diagnostic report has trailing whitespace:",
221:         "Failing command: in-memory source transformation",
222:         "Rollback result: application source/database/deployment were never intentionally modified",
223:         f"Final HEAD: {BASE_HEAD}",
224:         f"Final origin/main: {BASE_HEAD}",
225:         f"Final Alembic DB revision: {BASE_ALEMBIC}",
226:     )
227:     missing_failure_lines = [
228:         line for line in required_failure_lines if line not in patch743_failure
229:     ]
230:     require(
231:         not missing_failure_lines,
232:         f"Patch 743 failure evidence is incomplete: {missing_failure_lines!r}",
233:         phase,
234:     )
235:
236:     branch = state.run(["git", "branch", "--show-current"], phase).strip()
237:     require(branch == "main", f"Branch is not main: {branch!r}", phase)
238:     origin = state.run(["git", "remote", "get-url", "origin"], phase).strip()
239:     require(origin in EXPECTED_ORIGINS, f"Unexpected origin: {origin!r}", phase)
240:     state.run(["git", "fetch", "origin", "main"], phase, timeout=90)
241:
242:     head = state.run(["git", "rev-parse", "HEAD"], phase).strip()
```

Every required failure-summary line is absent from the exact Patch 743 tool log:

- `Patch 743 failed.`
- `Phase: diagnostic report write`
- `Diagnostic report has trailing whitespace:`
- `Failing command: in-memory source transformation`
- `Rollback result: application source/database/deployment were never intentionally modified`
- `Final HEAD: d79c7e5f1f66cef73ade6c5309ce41516f8c07b0`
- `Final origin/main: d79c7e5f1f66cef73ade6c5309ce41516f8c07b0`
- `Final Alembic DB revision: 0018_mcp_write_intents`

Those lines were printed to the terminal by Patch 743's top-level exception handler but were never appended to the tool log. Therefore Patch 744's predicate was impossible by construction.

### Patch 744 tool log

```text
[1/5] Validating exact clean Chat 25 boundary Git/index, consumed Patch 743 failure evidence, committed application bytes, healthy runtime, 0018 database and dynamic nine-key MCP policy shape
```

The Patch 744 log contains only phase `[1/5]` and no Git or Docker command entries, proving it stopped in preflight before the normal repository/runtime validation commands.

Patch 744 also inherited the Patch 743 log filename prefix:

```text
74:
75:
76: class State:
77:     def __init__(self) -> None:
78:         stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
79:         self.log = LOG_DIR / f"743_mcp_inventory_stock_write_anchor_diagnostic_{stamp}.log"
80:         self.phase = "initialization"
81:         self.last_command = "in-memory source transformation"
82:         self.last_stdout = ""
83:         self.last_stderr = ""
84:         self.report_written = False
```

That packaging defect explains why the Patch 744 log is named `743_mcp_inventory_stock_write_anchor_diagnostic_20260824-094806.log`. Patch 745 uses its own correct `745_...` log prefix.

## Inventory quantity-service source shape

The generic user/system audit fragment occurs `2` times at the same indentation in `parts.py`, and the actor expression occurs `3` times overall. It is not a safe textual anchor.

Canonical stock-adjustment block:

```text
1299: # PATCH 134: stock quantity adjustment and movement history service
1300: _ADJUSTMENT_MOVEMENT_TYPES = {
1301:     "add": MOVEMENT_TYPE_RESTOCK,
1302:     "remove": MOVEMENT_TYPE_ADJUST,
1303:     "consume": MOVEMENT_TYPE_CONSUME,
1304:     "correction": MOVEMENT_TYPE_ADJUST,
1305: }
1306:
1307: _DEFAULT_ADJUSTMENT_REASONS = {
1308:     "add": "Manual stock addition",
1309:     "remove": "Manual stock removal",
1310:     "consume": "Manual stock consumption",
1311:     "correction": "Manual stock correction",
1312: }
1313:
1314:
1315: def _adjustment_delta(payload: PartQuantityAdjustmentRequest) -> int:
1316:     if payload.operation == "add":
1317:         return payload.quantity
1318:     if payload.operation in {"remove", "consume"}:
1319:         return -payload.quantity
1320:     return payload.quantity
1321:
1322:
1323: def _serialize_stock_movement(
1324:     movement: StockMovement,
1325: ) -> StockMovementResponse:
1326:     return StockMovementResponse(
1327:         id=movement.id,
1328:         part_id=movement.part_id,
1329:         movement_type=movement.movement_type,
1330:         quantity_delta=movement.quantity_delta,
1331:         quantity_before=movement.quantity_before,
1332:         quantity_after=movement.quantity_after,
1333:         reserved_quantity_before=movement.reserved_quantity_before,
1334:         reserved_quantity_after=movement.reserved_quantity_after,
1335:         available_quantity_before=movement.available_quantity_before,
1336:         available_quantity_after=movement.available_quantity_after,
1337:         unit_price_snapshot=movement.unit_price_snapshot,
1338:         currency_snapshot=movement.currency_snapshot,
1339:         reason=movement.reason,
1340:         note=movement.note,
1341:         source=movement.source,
1342:         actor_user_id=movement.actor_user_id,
1343:         created_at=movement.created_at,
1344:     )
1345:
1346:
1347: def adjust_part_quantity(
1348:     db: Session,
1349:     part_id: int,
1350:     payload: PartQuantityAdjustmentRequest,
1351:     *,
1352:     actor_user_id: int | None = None,
1353:     commit: bool = True,
1354: ) -> PartQuantityAdjustmentResponse:
1355:     part = db.execute(
1356:         select(Part)
1357:         .where(
1358:             Part.id == part_id,
1359:             Part.is_deleted.is_(False),
1360:         )
1361:         .with_for_update()
1362:     ).scalar_one_or_none()
1363:     if part is None:
1364:         raise PartNotFoundError("Part not found.")
1365:
1366:     quantity_before = int(part.total_quantity)
1367:     quantity_delta = _adjustment_delta(payload)
1368:     quantity_after = quantity_before + quantity_delta
1369:
1370:     if quantity_after < 0:
1371:         raise PartValidationError(
1372:             "Quantity adjustment cannot reduce total stock below zero."
1373:         )
1374:     if quantity_after < part.reserved_quantity:
1375:         raise PartValidationError(
1376:             "Quantity adjustment cannot reduce total stock below the "
1377:             "reserved quantity."
1378:         )
1379:
1380:     movement_type = _ADJUSTMENT_MOVEMENT_TYPES[payload.operation]
1381:     reason = payload.reason or _DEFAULT_ADJUSTMENT_REASONS[payload.operation]
1382:     display_name = part.name or part.part_number or f"Part {part.id}"
1383:     available_before = quantity_before - part.reserved_quantity
1384:     available_after = quantity_after - part.reserved_quantity
1385:
1386:     movement = StockMovement(
1387:         part_id=part.id,
1388:         movement_type=movement_type,
1389:         quantity_delta=quantity_delta,
1390:         quantity_before=quantity_before,
1391:         quantity_after=quantity_after,
1392:         reserved_quantity_before=part.reserved_quantity,
1393:         reserved_quantity_after=part.reserved_quantity,
1394:         available_quantity_before=available_before,
1395:         available_quantity_after=available_after,
1396:         unit_price_snapshot=part.unit_price,
1397:         currency_snapshot=None,
1398:         reason=reason,
1399:         note=payload.note,
1400:         source=SOURCE_MANUAL,
1401:         actor_user_id=actor_user_id,
1402:     )
1403:
1404:     try:
1405:         part.total_quantity = quantity_after
1406:         db.add(movement)
1407:         db.flush()
1408:         db.add(
1409:             AuditLog(
1410:                 event_type="part.quantity_adjusted",
1411:                 entity_type="part",
1412:                 entity_id=part.id,
1413:                 actor_type=(
1414:                     "user" if actor_user_id is not None else "system"
1415:                 ),
1416:                 actor_user_id=actor_user_id,
1417:                 summary=(
1418:                     f"{payload.operation.title()} stock for {display_name}: "
1419:                     f"{quantity_before} to {quantity_after}"
```

Unique quantity-audit block:

```text
1405:         part.total_quantity = quantity_after
1406:         db.add(movement)
1407:         db.flush()
1408:         db.add(
1409:             AuditLog(
1410:                 event_type="part.quantity_adjusted",
1411:                 entity_type="part",
1412:                 entity_id=part.id,
1413:                 actor_type=(
1414:                     "user" if actor_user_id is not None else "system"
1415:                 ),
1416:                 actor_user_id=actor_user_id,
1417:                 summary=(
1418:                     f"{payload.operation.title()} stock for {display_name}: "
1419:                     f"{quantity_before} to {quantity_after}"
1420:                 ),
1421:                 before_json={
1422:                     "total_quantity": quantity_before,
1423:                     "reserved_quantity": part.reserved_quantity,
1424:                     "available_quantity": available_before,
1425:                 },
1426:                 after_json={
1427:                     "total_quantity": quantity_after,
1428:                     "reserved_quantity": part.reserved_quantity,
1429:                     "available_quantity": available_after,
1430:                 },
1431:                 metadata_json={
1432:                     "operation": payload.operation,
1433:                     "movement_type": movement_type,
1434:                     "quantity_delta": quantity_delta,
1435:                     "stock_movement_id": movement.id,
1436:                     "source": SOURCE_MANUAL,
1437:                     "reason": reason,
1438:                 },
1439:             )
1440:         )
1441:         db.flush()
1442:         if commit:
1443:             db.commit()
1444:             db.refresh(part)
1445:             db.refresh(movement)
```

Safe implementation rule: scope the MCP attribution change to the unique `adjust_part_quantity` function / `part.quantity_adjusted` audit block. Do not replace the generic actor fragment globally.

## Workspace registry source shape

```text
35: REDIRECT = "https://client.example/callback"
36: VERIFIER = "w" * 64
37: EXPECTED_TOOL_NAMES = (
38:     "get_part_details",
39:     "get_project_details",
40:     "get_reservation_details",
41:     "list_projects",
42:     "list_reservations",
43:     "search_parts",
44: )
45: REGISTERED_TOOL_NAMES = tuple(sorted((*EXPECTED_TOOL_NAMES,
46:     "reserve_project", "consume_reservation", "cancel_reservation")))
47:
48:
49: class SmokeFailure(RuntimeError):
50:     pass
51:
52:
```

Safe implementation rule: target the unique `REGISTERED_TOOL_NAMES = tuple(sorted((*EXPECTED_TOOL_NAMES, ...)))` assignment. Do not assume a separate write-tool set in this smoke.

## Existing safeguarded MCP write shape

```text
40:     get_reservation,
41: )
42:
43: # PARTPILOT:SAFEGUARDED_MCP_WRITE_TOOLS:V734
44: WRITE_TOOL_NAMES = ("reserve_project", "consume_reservation", "cancel_reservation")
45:
46: class WriteStockDelta(BaseModel):
47:     part_id: int
48:     part_number: str | None = None
49:     part_name: str | None = None
50:     units: int
51:     physical_before: int
52:     physical_after: int
53:     reserved_before: int
54:     reserved_after: int
55:     available_before: int
56:     available_after: int
57:
58: class WriteImpactPreview(BaseModel):
59:     action: Literal["reserve_project", "consume_reservation", "cancel_reservation"]
60:     target_type: Literal["project", "reservation"]
61:     target_id: int
62:     target_label: str
63:     status_before: str
64:     status_after: str
65:     linked_project_id: int | None = None
66:     linked_project_status_before: str | None = None
67:     linked_project_status_after: str | None = None
68:     total_units: int
69:     items: list[WriteStockDelta]
70:
71: class SafeguardedWriteResult(BaseModel):
```

The inventory stock tool should use a separate guarded runner so the approved Project/Reservation lifecycle runner is not refactored unnecessarily.

## MCP permission catalogue shape

```text
42:     capability: str
43:
44:
45: # PARTPILOT:MCP_WRITE_TOOL_CATALOGUE:V734
46: MCP_TOOL_CATALOGUE = (
47:     McpToolPermissionDefinition("search_parts", "Search parts", MCP_TOOL_CAPABILITY_READ),
48:     McpToolPermissionDefinition("get_part_details", "Get part details", MCP_TOOL_CAPABILITY_READ),
49:     McpToolPermissionDefinition("list_projects", "List Projects", MCP_TOOL_CAPABILITY_READ),
50:     McpToolPermissionDefinition("get_project_details", "Get Project details", MCP_TOOL_CAPABILITY_READ),
51:     McpToolPermissionDefinition("list_reservations", "List Reservations", MCP_TOOL_CAPABILITY_READ),
52:     McpToolPermissionDefinition("get_reservation_details", "Get Reservation details", MCP_TOOL_CAPABILITY_READ),
53:     McpToolPermissionDefinition("reserve_project", "Reserve Project", MCP_TOOL_CAPABILITY_WRITE),
54:     McpToolPermissionDefinition("consume_reservation", "Consume Reservation", MCP_TOOL_CAPABILITY_WRITE),
55:     McpToolPermissionDefinition("cancel_reservation", "Cancel Reservation", MCP_TOOL_CAPABILITY_WRITE),
56: )
57: MCP_TOOL_NAMES = tuple(item.name for item in MCP_TOOL_CATALOGUE)
58: MCP_TOOL_DEFINITIONS = {item.name: item for item in MCP_TOOL_CATALOGUE}
59: DEFAULT_MCP_TOOL_PERMISSIONS = {
60:     item.name: item.capability == MCP_TOOL_CAPABILITY_READ
61:     for item in MCP_TOOL_CATALOGUE
62: }
63:
64:
65: class McpToolPermissionError(RuntimeError):
66:     pass
67:
68:
69: class McpToolPermissionConfigurationError(McpToolPermissionError):
70:     pass
71:
72:
73: class McpToolPermissionDeniedError(McpToolPermissionError):
```

The global policy requires an exact key-set match. Adding `adjust_part_quantity` therefore requires a matching data migration.

## Current migration shape

```text
6: """
7: from __future__ import annotations
8:
9: import json
10:
11: from alembic import op
12: import sqlalchemy as sa
13:
14: # PARTPILOT:MCP_WRITE_INTENT_MIGRATION:V734
15: revision = "0018_mcp_write_intents"
16: down_revision = "0017_user_roles"
17: branch_labels = None
18: depends_on = None
19:
20: TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
21: READ_TOOLS = (
22:     "search_parts",
23:     "get_part_details",
24:     "list_projects",
25:     "get_project_details",
26:     "list_reservations",
27:     "get_reservation_details",
28: )
29: WRITE_TOOLS = (
30:     "reserve_project",
31:     "consume_reservation",
32:     "cancel_reservation",
33: )
34:
35:
36: def _verify_sqlite_foreign_keys(label: str) -> None:
37:     connection = op.get_bind()
38:     if connection.dialect.name != "sqlite":
39:         return
40:     violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
41:     if violations:
42:         raise RuntimeError(
43:             f"0018_mcp_write_intents {label} created foreign-key violations: {violations[:20]}"
44:         )
45:
46:
47: def _load_policy(connection, expected_keys: set[str]) -> dict[str, bool]:
48:     row = connection.execute(
49:         sa.text("SELECT value_json FROM app_settings WHERE key=:key"),
```

The next implementation patch must add data-only `0019_mcp_inventory_stock_write` with `down_revision="0018_mcp_write_intents"` and preserve all existing nine permission booleans dynamically while appending only `adjust_part_quantity: false`. Downgrade removes only that key. The critical schema fingerprint remains unchanged because 0019 changes only setting data.

Current seed fallback line:

```text
    "mcp.tool_permissions": {"value_json": {"search_parts": True, "get_part_details": True, "list_projects": True, "get_project_details": True, "list_reservations": True, "get_reservation_details": True}, "value_text": None},
```

The seed fallback may be updated to the canonical ten-tool policy: six read tools enabled and all four write tools disabled.

## Exact clean application fingerprints

- `backend/app/services/parts.py` — `24e4182083c86d4331e5368d48b31987137f191a55b113d5da01fb1355717cb3`
- `backend/app/mcp/write_tools.py` — `540bbaf760b555c80f0ee906146633587bfb28b15e9faf71b6ac6d0a000b7b39`
- `backend/app/services/mcp_permissions.py` — `5ef2969c6593d4e6a7c46fb118fe19fa7911fb8a26fe0f87b277ad306158b5d1`
- `backend/app/db/mcp_write_tools_smoke_test.py` — `a856fb9b33a1125b963c4ce8307476592d84235325af2d6cbbcb6b6c3504ded4`
- `backend/app/db/mcp_workspace_tools_smoke_test.py` — `bdc95fd17c255c717323b961fe13b70e453eddc2fba7e2bfd225c5c43222ccb2`
- `backend/app/services/backups.py` — `4bf3acd57f2dc28d6ea9db9365fcfbf304323dc6ed8661d1497493f15a722242`
- `backend/app/schemas/restores.py` — `1f84e2ef3a0e745654341d640489dc23efea21b18f6af893aa20772a7252c0b9`
- `backend/app/db/mcp_oauth_smoke_test.py` — `b7db18561dc1956604ff4996e2add42df549c5dda69067ca1e737698e6baa3a7`
- `backend/app/db/user_roles_smoke_test.py` — `9b6882a95ac259fb2b704d23cb2d32b8f4fb8a34403e435abc33c8af238ee566`
- `backend/app/db/seed.py` — `ae1bc273c74bdcf1aa09fb63294761a3271440dc438d8302ae253f551a856a9f`
- `backend/alembic/versions/0018_mcp_write_intents.py` — `60d44cbf8f874c06bf0d28954a7c43aabaf39c4ad7975b409267bdcd6c649636`

These hashes prove no pending implementation source survived Patches 743 or 744. After Patch 745's documentation-only commit, the next implementation patch must verify these same application bytes before writes rather than expecting HEAD itself to remain `d79c7e5f1f66cef73ade6c5309ce41516f8c07b0`.

## Safe Patch 747 implementation plan

Patch 747 may resume the first inventory-mutating MCP feature with a narrow stock-adjustment scope only:

1. `backend/app/services/parts.py`
   - factor canonical preview/planning math shared with mutation;
   - preserve existing zero/reserved floors;
   - preserve manual defaults;
   - add validated `actor_type`/`source` attribution for MCP confirmation.
2. `backend/app/mcp/write_tools.py`
   - add guarded `adjust_part_quantity`;
   - preview exact physical/reserved/available delta;
   - same idempotency key + short-lived confirmation token;
   - exact replay without second mutation/event;
   - publish only `inventory` + `history` after successful commit.
3. `backend/app/services/mcp_permissions.py`
   - add the fourth write-tool catalogue entry, disabled by default.
4. `backend/alembic/versions/0019_mcp_inventory_stock_write.py`
   - data-only 9 -> 10 permission migration preserving live booleans.
5. `backend/app/db/mcp_inventory_stock_write_smoke_test.py`
   - dedicated copied-production stock-write coverage.
6. Update exact current-head/tool registry/backup/restore/seed support files already identified by the diagnostic.

Expected bounded footprint remains twelve backend files; no frontend change is currently required because MCP permission rendering is catalogue-driven.

Patch 747 must construct all candidate transforms in memory first, use the unique function/block anchors documented here, run `git diff --check`, compile relevant Python, canonical Docker build, isolated 0018 -> 0019 -> 0018 -> 0019 migration rehearsal, copied-production MCP/security/backup/restore/complete smoke tests, and preserve production data. The new write permission remains disabled by default.

Create/edit inventory MCP tools move to later patches. Delete/restore remain deferred.

## Diagnostic conclusion

The current live application state is known and clean. Patch 743 and Patch 744 were patch-generation/recovery-layer failures, not application failures. Patch 746 recovers the consumed Patch 745 parser failure and provides the durable exact evidence required by the diagnostic-first rule. After this report is inspected, implementation can resume safely as Patch 747.
