# Duplicate Inventory Audit Event Diagnostic

<!-- PARTPILOT:DUPLICATE_AUDIT_DIAGNOSTIC:V291 -->

## Status

- Patch: 291
- Current HEAD: `e72e604f15f1dcbc22a8116b217ae59e4ab5574c`
- Application source modified: no
- Live database modified: no
- Deployment modified: no
- Isolated baseline smoke return code: `0`
- Isolated cleanup smoke return code: `1`
- Classification: **CLEANUP_SPECIFIC: baseline passes and the cleaned copy reproduces two audit events.**

## Patch 290 failure

Patch 290 completed direct cleanup evidence validation, fresh backups, a no-op
restart baseline, the real 70-row fixture deletion, and exact post-deletion
database verification before restart. Its post-cleanup smoke suite failed at:

```text
SmokeFailure: Created part did not create exactly one audit event: 2
```

Patch 290 restored its original database backup and restarted the service.

## Isolation method

Two SQLite copies were created with the SQLite backup API:

- Baseline copy: retained all 70 PP241 fixtures.
- Cleanup copy: removed exactly the 70 manifest-owned part IDs.

Each copy was mounted at `/data` in a disposable `docker compose run --rm`
container. The running Part Pilot container and live database were not used by
either smoke invocation.

## Baseline result

- Return code: `0`
- Audit count from failure: `None`
- Failure line: `(none)`

### Standard output

```text
[PASS] Database connection works
[PASS] SQLite foreign keys are enabled
[PASS] Alembic is at head: 0005_packages
[PASS] Built-in part types exist: 34
[PASS] Template fields exist: 157
[PASS] Default app settings exist: 17
[PASS] Invalid part without name/part number is rejected
[PASS] Valid sample part can be inserted and rolled back
[PASS] Backend DB utilities work
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth service works
[PASS] Phase 3 auth API routes are registered
[PASS] Phase 3 auth and application setup API flow works
[PASS] Phase 4 part type service returns seeded templates
[PASS] Phase 4 part type API is protected and returns templates
[PASS] Custom part types can be created with validated ordered fields
[PASS] Custom part types can be edited with protected ordered fields
[PASS] Custom part types delete safely with inventory usage safeguards
[PASS] Inventory parts can be created with validated dynamic fields
[PASS] Reusable manufacturer catalogue is seeded and extensible
[PASS] Reusable package catalogue is seeded and extensible
[PASS] Reusable location catalogue is authenticated, normalized, editable, usage-aware, safe for active and deleted part references, and audited
[PASS] Part creation and metadata editing support reusable location assignment, change, clearing, serialization, and complete audits
[PASS] Stored Parts supports authenticated location filtering with correct totals, pagination, combined filters, serialization, unassigned parts, and deleted-part exclusion
[PASS] Protected search settings persist and audit actual changes; low-stock summary handles configured and unconfigured zero stock, reservations, thresholds, disabled positive stock, deleted rows, filters, limits, counts, and deterministic severity ordering
[PASS] Stored Parts independently sorts Available and Out of stock sections without changing the other section
[PASS] Stored Parts server-backed sorting covers every supported column, both directions, pagination, and validation
[PASS] Protected universal part search covers metadata, type, manufacturer, location, aliases, tags, custom text/numeric/boolean values and field labels; preserves type, location, and stock-status filters, totals, pagination, literal wildcards, case-insensitive partial matching, duplicate suppression, deleted exclusion, and available-first deterministic ordering and server-backed sortable columns
[PASS] Stock quantity adjustments are authenticated, atomic, guarded, audited, and exposed through recent history
[PASS] Existing part metadata updates are authenticated, typed, atomic, quantity-safe, duplicate-safe, and audited
[PASS] Part soft deletion and restoration are authenticated, reversible, retention-safe, duplicate-safe, hidden from active reads, and audited
[PASS] Phase 4 part type management smoke test completed
```

### Standard error

```text
 Container partpilot-partpilot-run-acc794223050 Creating
 Container partpilot-partpilot-run-acc794223050 Created
/usr/local/lib/python3.12/site-packages/anyio/_backends/_asyncio.py:1033: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
  result = context.run(func, *args)
/usr/local/lib/python3.12/site-packages/anyio/_backends/_asyncio.py:1033: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
  result = context.run(func, *args)
/usr/local/lib/python3.12/site-packages/anyio/_backends/_asyncio.py:1033: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
  result = context.run(func, *args)
```

### Database changes

### `app_settings`

- Removed rows: 1
- Added rows: 1


Removed examples:


```json
{"created_at":"2026-07-23 14:34:29.699952","id":7,"key":"search.show_out_of_stock_section","updated_at":"2026-07-27 17:34:44.007039","value_json":"true","value_text":null}
```


Added examples:


```json
{"created_at":"2026-07-23 14:34:29.699952","id":7,"key":"search.show_out_of_stock_section","updated_at":"2026-07-28 12:12:14.117735","value_json":"true","value_text":null}
```

### Audit-related changes

No database rows changed.

## Cleanup result

- Return code: `1`
- Audit count from failure: `2`
- Failure line: `SmokeFailure: Created part did not create exactly one audit event: 2`

### Standard output

```text
[PASS] Database connection works
[PASS] SQLite foreign keys are enabled
[PASS] Alembic is at head: 0005_packages
[PASS] Built-in part types exist: 34
[PASS] Template fields exist: 157
[PASS] Default app settings exist: 17
[PASS] Invalid part without name/part number is rejected
[PASS] Valid sample part can be inserted and rolled back
[PASS] Backend DB utilities work
[PASS] Phase 3 auth foundation works
[PASS] Phase 3 auth service works
[PASS] Phase 3 auth API routes are registered
[PASS] Phase 3 auth and application setup API flow works
[PASS] Phase 4 part type service returns seeded templates
[PASS] Phase 4 part type API is protected and returns templates
[PASS] Custom part types can be created with validated ordered fields
[PASS] Custom part types can be edited with protected ordered fields
[PASS] Custom part types delete safely with inventory usage safeguards
```

### Standard error

```text
 Container partpilot-partpilot-run-adcadc18e18d Creating
 Container partpilot-partpilot-run-adcadc18e18d Created
/usr/local/lib/python3.12/site-packages/anyio/_backends/_asyncio.py:1033: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
  result = context.run(func, *args)
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/app/backend/app/db/smoke_test.py", line 7050, in <module>
    main()
  File "/app/backend/app/db/smoke_test.py", line 7044, in main
    check()
  File "/app/backend/app/db/smoke_test.py", line 1859, in check_inventory_part_creation_api
    fail(
  File "/app/backend/app/db/smoke_test.py", line 60, in fail
    raise SmokeFailure(message)
SmokeFailure: Created part did not create exactly one audit event: 2
```

### Database changes

### `audit_log`

- Removed rows: 1
- Added rows: 0


Removed examples:


```json
{"actor_type":"system","actor_user_id":null,"after_json":"{\"id\": 10, \"part_type_id\": 22, \"part_type_name\": \"Buzzer\", \"manufacturer_id\": 2, \"manufacturer_name\": \"Arduino\", \"location_id\": 1, \"location_name\": \"Box A1\", \"part_number\": \"PP241-20260727-075829-0F182174-001\", \"name\": \"PP241-20260727-075829-0F182174 Fixture 001 - Buzzer\", \"total_quantity\": 13, \"unit_price\": \"2.07\", \"field_value_count\": 0}","before_json":"null","created_at":"2026-07-27 07:58:44.051116","entity_id":10,"entity_type":"part","event_type":"part.created","id":36,"metadata_json":"{\"part_type_id\": 22, \"part_type_name\": \"Buzzer\"}","summary":"Created inventory part PP241-20260727-075829-0F182174 Fixture 001 - Buzzer"}
```

### Audit-related changes

### `audit_log`

- Removed rows: 1
- Added rows: 0


Removed examples:


```json
{"actor_type":"system","actor_user_id":null,"after_json":"{\"id\": 10, \"part_type_id\": 22, \"part_type_name\": \"Buzzer\", \"manufacturer_id\": 2, \"manufacturer_name\": \"Arduino\", \"location_id\": 1, \"location_name\": \"Box A1\", \"part_number\": \"PP241-20260727-075829-0F182174-001\", \"name\": \"PP241-20260727-075829-0F182174 Fixture 001 - Buzzer\", \"total_quantity\": 13, \"unit_price\": \"2.07\", \"field_value_count\": 0}","before_json":"null","created_at":"2026-07-27 07:58:44.051116","entity_id":10,"entity_type":"part","event_type":"part.created","id":36,"metadata_json":"{\"part_type_id\": 22, \"part_type_name\": \"Buzzer\"}","summary":"Created inventory part PP241-20260727-075829-0F182174 Fixture 001 - Buzzer"}
```

## Classification

**CLEANUP_SPECIFIC: baseline passes and the cleaned copy reproduces two audit events.**

## Relevant source excerpts

### `backend/app/db/session.py`

Total matching excerpts: 1

Line 19:

```text
0016: )
0017:
0018:
0019: @event.listens_for(engine, "connect")
0020: def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
0021:     if settings.database_url.startswith("sqlite"):
0022:         cursor = dbapi_connection.cursor()
0023:         cursor.execute("PRAGMA foreign_keys=ON")
0024:         cursor.close()
```
### `backend/app/db/smoke_test.py`

Total matching excerpts: 11

Line 1257:

```text
1254:         if audit_count != 1:
1255:             fail(
1256:                 "Custom part type update did not create exactly one "
1257:                 f"audit event: {audit_count!r}"
1258:             )
1259:
1260:     finally:
1261:         cleanup()
1262:
```

Line 1484:

```text
1481:         if audit_count != 1:
1482:             fail(
1483:                 "Custom part type deletion did not create exactly one "
1484:                 f"audit event: {audit_count!r}"
1485:             )
1486:
1487:     finally:
1488:         cleanup()
1489:
```

Line 1495:

```text
1492:     )
1493:
1494: # PATCH 093: inventory part creation API smoke test
1495: def check_inventory_part_creation_api() -> None:
1496:     from fastapi.testclient import TestClient
1497:
1498:     from app.main import app as fastapi_app
1499:
1500:     username = "smoke_inventory_part_user"
```

Line 1860:

```text
1857:             )
1858:         if audit_count != 1:
1859:             fail(
1860:                 "Created part did not create exactly one audit event: "
1861:                 f"{audit_count!r}"
1862:             )
1863:
1864:     finally:
1865:         cleanup()
```

Line 2022:

```text
2019:         if audit_count != 1:
2020:             fail(
2021:                 "Manufacturer creation did not create exactly one "
2022:                 f"audit event: {audit_count!r}"
2023:             )
2024:
2025:     finally:
2026:         cleanup()
2027:
```

Line 3178:

```text
3175:             )
3176:         if len(audit_rows) != 1:
3177:             fail(
3178:                 "Metadata editing should create exactly one audit event, got "
3179:                 f"{len(audit_rows)}."
3180:             )
3181:
3182:         audit_row = audit_rows[0]
3183:         if audit_row[0] != user_id:
```

Line 3605:

```text
3602:             )
3603:         if len(deletion_audits) != 1:
3604:             fail(
3605:                 "Soft deletion should create exactly one audit event, got "
3606:                 f"{len(deletion_audits)}."
3607:             )
3608:
3609:         deletion_audit = deletion_audits[0]
3610:         deletion_before = (
```

Line 3767:

```text
3764:             )
3765:         if len(restoration_audits) != 1:
3766:             fail(
3767:                 "Restoration should create exactly one audit event, got "
3768:                 f"{len(restoration_audits)}."
3769:             )
3770:
3771:         restoration_audit = restoration_audits[0]
3772:         restoration_before = (
```
### `backend/app/models/core.py`

Total matching excerpts: 1

Line 30:

```text
0027:     return datetime.now(timezone.utc)
0028:
0029:
0030: @event.listens_for(Engine, "connect")
0031: def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
0032:     """Ensure SQLite enforces foreign-key constraints.
0033:
0034:     SQLite accepts foreign-key definitions but does not enforce them unless
0035:     PRAGMA foreign_keys=ON is set per connection.
```

## Safe next step

Patch 292 must use this classification:

- `TRANSIENT`: retry cleanup with the same direct database checks, but run the
  isolated smoke suite before touching the live database and proceed only when
  both isolated copies pass.
- `BASELINE`: fix or isolate the duplicate audit registration/test behaviour
  before attempting fixture cleanup again.
- `CLEANUP_SPECIFIC`: inspect the exact database and source differences in this
  report before changing cleanup logic.
- `BASELINE_ONLY` or `MIXED`: issue a narrow diagnostic/fix based on the captured
  source excerpts and database diffs.

Do not create a next-chat prompt. Chat 11 remains active until boundary recovery
actually finishes with `Everything PASS`.
