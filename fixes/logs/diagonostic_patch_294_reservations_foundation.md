# Patch 294 Reservation Architecture Diagnostic

<!-- PARTPILOT:RESERVATION_ARCHITECTURE_DIAGNOSTIC:V294 -->

Generated: `2026-07-28T14:44:53.052834+00:00`

## Scope and preservation

This is a diagnostic-only checkpoint. It inspected the exact local repository,
running container, live SQLite schema and row counts, protected API behaviour,
frontend placeholders, and reusable inventory structures.

It did **not** modify application source, the live database, inventory,
fixtures, deployment, or container state. It did not build or restart the
application and did not run the mutating smoke suite against the live database.

Only this report is intended to be committed.

## Verified checkpoint

- Branch: `main`
- Starting HEAD: `a781003da7d10ee1e6d48196882af090a3f8705c`
- Origin: `github.com/devanshtangri/Part-Pilot`
- Alembic: `0005_packages`
- Container: `partpilot`
- Container ID: `5f84a320d363`
- Image: `partpilot-partpilot`
- Live database: `/projects/Part Pilot/data/partpilot.db`
- Database snapshot SHA-256: `d5e62c4351892a24f221756efdeba272891b09571d3de2677159eb034fd5f644`
- SQLite integrity: `ok`
- Foreign-key violations: `0`

## Executive findings

1. `projects`, `project_items`, `reservations`, and `reservation_items` already
   exist and are empty.
2. The ORM exports all four model classes and defines foreign-key columns, but
   none of the inspected classes has an ORM `relationship()` mapping.
3. No reservation or project schema, service, or API route files exist, and no
   routers are registered for either resource.
4. `/projects` and `/reservations` are authenticated frontend placeholder
   routes. `/api/projects` and `/api/reservations` return JSON `404`.
5. The canonical stock formula is
   `available_quantity = total_quantity - reserved_quantity`.
6. Live `parts` constraints prevent negative total/reserved stock and prevent
   `reserved_quantity > total_quantity`.
7. **The status contract is inconsistent.** ORM model values, constants, and
   the live migrated schema do not agree. The live project and reservation
   tables have no status CHECK constraints.
8. Existing stock movements describe physical `total_quantity` changes.
   Reservation creation/cancellation changes `reserved_quantity`, so movement
   semantics must be defined before implementation rather than overloading
   existing fields ambiguously.
9. Projects must remain outside the initial implementation boundary. The
   nullable `project_id` can remain stored and returned, but reservation
   creation should not create, edit, or validate project workflows yet.

## Live table state

| Table | Rows | CHECK constraints | Foreign keys | Indexes |
| --- | --- | --- | --- | --- |
| parts | 9 | ck_parts_name_or_part_number, ck_parts_reserved_lte_total, ck_parts_reserved_quantity_nonnegative, ck_parts_total_quantity_nonnegative | part_type_id → part_types.id (RESTRICT); location_id → locations.id (SET NULL); manufacturer_id → manufacturers.id (SET NULL) | ix_parts_manufacturer_id(manufacturer_id); ix_parts_part_type_deleted(part_type_id, is_deleted); ix_parts_location_id(location_id); ix_parts_part_number(part_number); ix_parts_is_deleted(is_deleted); ix_parts_package(package); ix_parts_location_deleted(location_id, is_deleted); ix_parts_name(name); ix_parts_part_type_id(part_type_id); sqlite_autoindex_parts_1(part_number) UNIQUE |
| stock_movements | 4 | None | actor_user_id → users.id (SET NULL); part_id → parts.id (SET NULL) | ix_stock_movements_part_created(part_id, created_at); ix_stock_movements_movement_type(movement_type); ix_stock_movements_part_id(part_id) |
| audit_log | 35 | None | actor_user_id → users.id (SET NULL) | ix_audit_log_event_created(event_type, created_at); ix_audit_log_entity(entity_type, entity_id); ix_audit_log_entity_id(entity_id); ix_audit_log_entity_type(entity_type); ix_audit_log_event_type(event_type); ix_audit_log_created_at(created_at) |
| projects | 0 | None | None | ix_projects_status(status); ix_projects_name(name) |
| project_items | 0 | ck_project_items_quantity_positive | part_id → parts.id (SET NULL); project_id → projects.id (CASCADE) | ix_project_items_project_part(project_id, part_id); ix_project_items_part_id(part_id); ix_project_items_project_id(project_id) |
| reservations | 0 | None | project_id → projects.id (SET NULL) | ix_reservations_status(status); ix_reservations_label(label); ix_reservations_project_id(project_id) |
| reservation_items | 0 | ck_reservation_items_quantity_positive | part_id → parts.id (SET NULL); reservation_id → reservations.id (CASCADE) | ix_reservation_items_reservation_part(reservation_id, part_id); ix_reservation_items_part_id(part_id); ix_reservation_items_reservation_id(reservation_id) |

Current active inventory totals:

- Active parts: `7`
- Total quantity: `144`
- Reserved quantity: `0`
- Available quantity: `144`
- Parts with reserved quantity: `0`

The four project/reservation tables are empty, so the reservation foundation can
be introduced without data migration for existing reservation rows. Real
inventory must still be preserved exactly.

## Model, constants and live-schema mismatch

| Resource | ORM values | Constants | Live database |
| --- | --- | --- | --- |
| Project | cancelled, consumed, draft, reserved | active, archived, completed, draft | No live status CHECK |
| Reservation | active, cancelled, consumed, expired | active, consumed, expired, released | No live status CHECK |

### Required contract decision

Use one reservation vocabulary consistently across constants, ORM, migration,
schemas, service, API and smoke tests:

- `active`
- `consumed`
- `cancelled`
- `expired`

`cancelled` matches the current ORM and the requested API lifecycle. The current
constant `released` should not become a second terminal status. `release` remains
an appropriate **movement type** for returning reserved units to availability.

Project status vocabulary is also inconsistent, but Projects are not being
implemented in this boundary. Do not silently normalize Project statuses as part
of reservation work. Record that as a later Projects-specific migration and
contract decision.

### ORM relationship state

| Model | relationship() calls | Finding |
| --- | --- | --- |
| Part | 0 | Foreign-key columns only; no ORM relationship() mapping |
| StockMovement | 0 | Foreign-key columns only; no ORM relationship() mapping |
| Project | 0 | Foreign-key columns only; no ORM relationship() mapping |
| ProjectItem | 0 | Foreign-key columns only; no ORM relationship() mapping |
| Reservation | 0 | Foreign-key columns only; no ORM relationship() mapping |
| ReservationItem | 0 | Foreign-key columns only; no ORM relationship() mapping |
| AuditLog | 0 | Foreign-key columns only; no ORM relationship() mapping |

Foreign-key columns are sufficient for narrow service queries, but explicit ORM
relationships may be added later only when their loading/cascade behaviour is
deliberately defined. They are not required to start the reservation service.

## Existing quantity semantics

The stored fields are:

- `Part.total_quantity`: physical stock currently held.
- `Part.reserved_quantity`: stock allocated to active reservations.
- `Part.available_quantity`: computed response value, never stored.
- Formula: `total_quantity - reserved_quantity`.

Relevant utility:

```text
   47: def available_quantity(total_quantity: int, reserved_quantity: int) -> int:
   48:     """Compute available quantity from stored total and reserved counts."""
   49:     return int(total_quantity) - int(reserved_quantity)
```

The part serializer computes available stock from stored total and reserved
counts. Low-stock and out-of-stock presentation also uses available quantity.

```text
  173: def _serialize_part(db: Session, part: Part) -> PartResponse:
  174:     part_type = db.get(PartType, part.part_type_id)
  175:     if part_type is None:
  176:         raise PartNotFoundError("Part type not found.")
  177:
  178:     manufacturer = (
  179:         db.get(Manufacturer, part.manufacturer_id)
  180:         if part.manufacturer_id is not None
  181:         else None
  182:     )
  183:
  184:     location = (
  185:         db.get(Location, part.location_id)
  186:         if part.location_id is not None
  187:         else None
  188:     )
  189:     fields = list(
  190:         db.execute(
  191:             select(PartTypeField)
  192:             .where(PartTypeField.part_type_id == part.part_type_id)
  193:             .order_by(
  194:                 PartTypeField.sort_order.asc(),
  195:                 PartTypeField.id.asc(),
  196:             )
  197:         ).scalars()
  198:     )
  199:     field_map = {field.id: field for field in fields}
  200:
  201:     values = list(
  202:         db.execute(
  203:             select(PartFieldValue)
  204:             .where(PartFieldValue.part_id == part.id)
  205:             .order_by(PartFieldValue.id.asc())
  206:         ).scalars()
  207:     )
  208:
  209:     field_values: list[PartFieldValueResponse] = []
  210:     for value in values:
  211:         field = field_map.get(value.field_id)
  212:         if field is None:
  213:             continue
  214:
  215:         field_values.append(
  216:             PartFieldValueResponse(
  217:                 id=value.id,
  218:                 field_id=field.id,
  219:                 field_key=field.field_key,
  220:                 label=field.label,
  221:                 field_type=field.field_type,
  222:                 is_required=field.is_required,
  223:                 value_text=value.value_text,
  224:                 value_number=value.value_number,
  225:                 value_bool=value.value_bool,
  226:                 unit=value.unit,
  227:             )
  228:         )
  229:
  230:     available_quantity = part.total_quantity - part.reserved_quantity
  231:     is_low_stock = bool(
  232:         part.low_stock_enabled
  233:         and part.low_stock_threshold is not None
  234:         and available_quantity <= part.low_stock_threshold
  235:     )
  236:
  237:     return PartResponse(
  238:         id=part.id,
  239:         part_type_id=part.part_type_id,
  240:         part_type_name=part_type.name,
  241:         manufacturer_id=part.manufacturer_id,
  242:         manufacturer_name=(
  243:             manufacturer.name
  244:             if manufacturer is not None
  245:             else None
  246:         ),
  247:         location_id=part.location_id,
  248:         location_name=(
  249:             location.name
  250:             if location is not None
  251:             else None
  252:         ),
  253: ... excerpt truncated ...
```

The current manual quantity-adjustment service rejects any total reduction below
the reserved quantity. It uses `.with_for_update()`, creates one physical stock
movement, writes a structured audit record, and commits or rolls back as one
unit.

```text
 1283: def adjust_part_quantity(
 1284:     db: Session,
 1285:     part_id: int,
 1286:     payload: PartQuantityAdjustmentRequest,
 1287:     *,
 1288:     actor_user_id: int | None = None,
 1289:     commit: bool = True,
 1290: ) -> PartQuantityAdjustmentResponse:
 1291:     part = db.execute(
 1292:         select(Part)
 1293:         .where(
 1294:             Part.id == part_id,
 1295:             Part.is_deleted.is_(False),
 1296:         )
 1297:         .with_for_update()
 1298:     ).scalar_one_or_none()
 1299:     if part is None:
 1300:         raise PartNotFoundError("Part not found.")
 1301:
 1302:     quantity_before = int(part.total_quantity)
 1303:     quantity_delta = _adjustment_delta(payload)
 1304:     quantity_after = quantity_before + quantity_delta
 1305:
 1306:     if quantity_after < 0:
 1307:         raise PartValidationError(
 1308:             "Quantity adjustment cannot reduce total stock below zero."
 1309:         )
 1310:     if quantity_after < part.reserved_quantity:
 1311:         raise PartValidationError(
 1312:             "Quantity adjustment cannot reduce total stock below the "
 1313:             "reserved quantity."
 1314:         )
 1315:
 1316:     movement_type = _ADJUSTMENT_MOVEMENT_TYPES[payload.operation]
 1317:     reason = payload.reason or _DEFAULT_ADJUSTMENT_REASONS[payload.operation]
 1318:     display_name = part.name or part.part_number or f"Part {part.id}"
 1319:     available_before = quantity_before - part.reserved_quantity
 1320:     available_after = quantity_after - part.reserved_quantity
 1321:
 1322:     movement = StockMovement(
 1323:         part_id=part.id,
 1324:         movement_type=movement_type,
 1325:         quantity_delta=quantity_delta,
 1326:         quantity_before=quantity_before,
 1327:         quantity_after=quantity_after,
 1328:         unit_price_snapshot=part.unit_price,
 1329:         currency_snapshot=None,
 1330:         reason=reason,
 1331:         note=payload.note,
 1332:         source=SOURCE_MANUAL,
 1333:         actor_user_id=actor_user_id,
 1334:     )
 1335:
 1336:     try:
 1337:         part.total_quantity = quantity_after
 1338:         db.add(movement)
 1339:         db.flush()
 1340:         db.add(
 1341:             AuditLog(
 1342:                 event_type="part.quantity_adjusted",
 1343:                 entity_type="part",
 1344:                 entity_id=part.id,
 1345:                 actor_type=(
 1346:                     "user" if actor_user_id is not None else "system"
 1347:                 ),
 1348:                 actor_user_id=actor_user_id,
 1349:                 summary=(
 1350:                     f"{payload.operation.title()} stock for {display_name}: "
 1351:                     f"{quantity_before} to {quantity_after}"
 1352:                 ),
 1353:                 before_json={
 1354:                     "total_quantity": quantity_before,
 1355:                     "reserved_quantity": part.reserved_quantity,
 1356:                     "available_quantity": available_before,
 1357:                 },
 1358:                 after_json={
 1359:                     "total_quantity": quantity_after,
 1360:                     "reserved_quantity": part.reserved_quantity,
 1361:                     "available_quantity": available_after,
 1362:                 },
 1363:                 metadata_json={
 1364:                     "operation": payload.operation,
 1365:                     "movement_type": movement_type,
 1366:                     "quantity_delta": quantity_delta,
 1367:                     "stock_movement_id": movement.id,
 1368:                     "source": SOURCE_MANUAL,
 1369:                     "reason": reason,
 1370:                 },
 1371:             )
 1372:         )
 1373: ... excerpt truncated ...
```

### Concurrency boundary for reservation creation

Do not implement reservation creation as only:

1. read available quantity;
2. compare in Python;
3. increment `reserved_quantity`.

That sequence can oversubscribe under concurrent requests. For SQLite, use one
transaction with a guarded update per part, equivalent to:

```sql
UPDATE parts
SET reserved_quantity = reserved_quantity + :requested
WHERE id = :part_id
  AND is_deleted = 0
  AND total_quantity - reserved_quantity >= :requested;
```

Require exactly one affected row for every requested part. If any guarded update
fails, roll back the reservation, all item rows, all reserved counters, all
movement rows and all audit rows.

Normalize duplicate input part IDs before the transaction. The current composite
reservation-item index is non-unique; the service should reject duplicates or
aggregate them into one item per part. A future migration may make
`(reservation_id, part_id)` unique after deciding whether historical item rows
may retain `part_id = NULL`.

## Reservation lifecycle boundaries

### Creation

Creation should:

- require authentication;
- require a non-empty label;
- require at least one item;
- require positive integer quantities;
- reject deleted or missing parts;
- reject any request exceeding available quantity;
- create one `active` reservation and normalized item rows;
- increment each part's `reserved_quantity` atomically;
- snapshot unit price and configured currency;
- create structured audit and movement/history records;
- commit all effects together.

### Cancellation

Only `active -> cancelled` is valid.

Cancellation should:

- be idempotency-safe by rejecting a second transition with `409`;
- decrement each affected part's `reserved_quantity` by the exact stored item
  quantity;
- leave `total_quantity` unchanged;
- increase available quantity by the released quantity;
- write release movements and a reservation cancellation audit;
- keep reservation and item rows for history;
- commit all effects together.

A missing part reference caused by `ON DELETE SET NULL` must not silently skip
counter release. Active reservations should prevent part deletion, or the
reservation service must preserve enough immutable identity to release safely.
The safer initial rule is: a part with active reservation quantity cannot be
soft-deleted.

### Consumption

Consumption is a separate lifecycle slice after creation/cancellation tests pass.

For each item:

- `total_quantity -= quantity`;
- `reserved_quantity -= quantity`;
- available quantity remains unchanged;
- write physical consume movement plus reservation consumption audit;
- transition only `active -> consumed`.

Do not reuse the existing manual quantity-adjustment endpoint to consume a
reservation; the reservation service must update the reservation and all parts
in one transaction.

### Expiry

Expiry is not a background scheduler in the first slice.

Define one deterministic service operation that:

- selects active reservations with `expiry_at <= now`;
- performs the same counter release as cancellation;
- transitions `active -> expired`;
- writes system-actor release movements and audit records;
- is safe to run repeatedly.

Automatic scheduling can be added later without changing the lifecycle
transaction.

### Project linking boundary

The database already permits `reservations.project_id` with `ON DELETE SET NULL`.

For the initial reservation contract:

- return `project_id` as nullable;
- do not create or modify Projects;
- do not expose project editing;
- omit `project_id` from create payloads, or accept only `null`;
- do not infer project state from reservation state.

Enable non-null project linking only after the Projects service and lifecycle
rules are separately verified.

## Movement and audit contract

Current movement constants already include `reserve`, `release`, and `consume`.
However, existing `StockMovement.quantity_before`, `quantity_after`, and
`quantity_delta` are used for physical total stock.

A reservation movement contract must not reinterpret those fields as available
stock for only some movement types.

Recommended narrow migration before the reservation API:

- add nullable `reservation_id` to `stock_movements`;
- add nullable `reserved_quantity_before`;
- add nullable `reserved_quantity_after`;
- add nullable `available_quantity_before`;
- add nullable `available_quantity_after`;
- keep existing `quantity_*` fields as physical total quantity;
- index `(reservation_id, created_at)` and preserve existing part history order.

Then record:

- reserve: physical delta `0`, reserved delta positive, available delta negative;
- release/cancel/expire: physical delta `0`, reserved delta negative, available
  delta positive;
- consume: physical delta negative, reserved delta negative, available delta `0`.

Audit event names should remain structured and stable:

- `reservation.created`
- `reservation.cancelled`
- `reservation.consumed`
- `reservation.expired`

Each reservation audit should use `entity_type="reservation"`, the reservation
ID, the authenticated actor for manual actions, and metadata containing affected
part IDs, item quantities, movement IDs and before/after quantity snapshots.

## Existing service and protected-route conventions

Authentication dependency:

```text
   56: def get_current_user(
   57:     authorization: str | None = Header(default=None),
   58:     db: Session = Depends(get_db),
   59: ):
   60:     token = _extract_bearer_token(authorization)
   61:     user = get_user_for_session_token(db, token)
   62:
   63:     if user is None:
   64:         raise HTTPException(
   65:             status_code=status.HTTP_401_UNAUTHORIZED,
   66:             detail="Invalid or expired session",
   67:         )
   68:
   69:     return user
```

Representative protected create route:

```text
  144: def create_inventory_part(
  145:     payload: PartCreateRequest,
  146:     current_user=Depends(get_current_user),
  147:     db: Session = Depends(get_db),
  148: ) -> PartResponse:
  149:     try:
  150:         return create_part(
  151:             db,
  152:             payload,
  153:             actor_user_id=current_user.id,
  154:             commit=True,
  155:         )
  156:     except PartConflictError as exc:
  157:         raise HTTPException(
  158:             status_code=status.HTTP_409_CONFLICT,
  159:             detail=str(exc),
  160:         ) from exc
  161:     except PartValidationError as exc:
  162:         raise HTTPException(
  163:             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
  164:             detail=str(exc),
  165:         ) from exc
```

Reservation routes should follow the same conventions:

- `APIRouter(prefix="/reservations", tags=["reservations"])`;
- `Depends(get_current_user)` on every endpoint;
- Pydantic request/response models;
- service-specific not-found, conflict and validation exceptions;
- `404` for missing resources;
- `409` for lifecycle or availability conflicts;
- `422` for invalid payload semantics;
- service functions supporting `commit: bool = True`;
- rollback on every failed multi-row write.

Initial protected endpoints:

- `GET /api/reservations`
- `GET /api/reservations/{reservation_id}`
- `POST /api/reservations`
- `POST /api/reservations/{reservation_id}/cancel`

Consumption and expiry execution should be added only after the initial contract
is verified.

## Smoke-test conventions

The smoke suite currently has `31` top-level
functions and `15` local `cleanup()`
functions. It uses unique `uuid4()` suffixes, protected TestClient requests,
exact fixture IDs, explicit pre-cleanup, `try/finally`, and exact post-cleanup.

Reservation/project smoke functions currently present:
`none`.

Representative inventory API fixture/cleanup structure:

```text
 1495: def check_inventory_part_creation_api() -> None:
 1496:     from fastapi.testclient import TestClient
 1497:
 1498:     from app.main import app as fastapi_app
 1499:
 1500:     username = "smoke_inventory_part_user"
 1501:     password = "inventory-part-smoke-password"
 1502:     custom_type_id: int | None = None
 1503:     created_part_id: int | None = None
 1504:
 1505:     def cleanup() -> None:
 1506:         with db_session() as db:
 1507:             if created_part_id is not None:
 1508:                 db.execute(
 1509:                     text(
 1510:                         "delete from audit_log "
 1511:                         "where entity_type = 'part' "
 1512:                         "and entity_id = :entity_id"
 1513:                     ),
 1514:                     {"entity_id": created_part_id},
 1515:                 )
 1516:                 db.execute(
 1517:                     text(
 1518:                         "delete from part_field_values "
 1519:                         "where part_id = :part_id"
 1520:                     ),
 1521:                     {"part_id": created_part_id},
 1522:                 )
 1523:                 db.execute(
 1524:                     text(
 1525:                         "delete from parts where id = :part_id"
 1526:                     ),
 1527:                     {"part_id": created_part_id},
 1528:                 )
 1529:
 1530:             if custom_type_id is not None:
 1531:                 db.execute(
 1532:                     text(
 1533:                         "delete from audit_log "
 1534:                         "where entity_type = 'part_type' "
 1535:                         "and entity_id = :entity_id"
 1536:                     ),
 1537:                     {"entity_id": custom_type_id},
 1538:                 )
 1539:                 db.execute(
 1540:                     text(
 1541:                         "delete from part_type_fields "
 1542:                         "where part_type_id = :part_type_id"
 1543:                     ),
 1544:                     {"part_type_id": custom_type_id},
 1545:                 )
 1546:                 db.execute(
 1547:                     text(
 1548:                         "delete from part_types "
 1549:                         "where id = :part_type_id"
 1550:                     ),
 1551:                     {"part_type_id": custom_type_id},
 1552:                 )
 1553:
 1554:             db.execute(
 1555:                 text(
 1556:                     "delete from sessions where user_id in "
 1557:                     "(select id from users where username = :username)"
 1558:                 ),
 1559:                 {"username": username},
 1560:             )
 1561:             db.execute(
 1562:                 text(
 1563:                     "delete from users where username = :username"
 1564:                 ),
 1565:                 {"username": username},
 1566:             )
 1567:             db.commit()
 1568:
 1569:     cleanup()
 1570:     client = TestClient(fastapi_app)
 1571:
 1572:     try:
 1573:         with db_session() as db:
 1574:             user = create_user(
 1575:                 db,
 1576:                 username=username,
 1577:                 display_name="Inventory Part Smoke User",
 1578:                 password=password,
 1579:                 commit=True,
 1580:             )
 1581:             session_token = create_session(
 1582:                 db,
 1583:                 user=user,
 1584:                 commit=True,
 1585: ... excerpt truncated ...
```

Representative quantity and movement assertions:

```text
 2195: def check_stock_quantity_adjustment_api() -> None:
 2196:     from fastapi.testclient import TestClient
 2197:
 2198:     from app.main import app as fastapi_app
 2199:
 2200:     username = "smoke_stock_adjustment_user"
 2201:     password = "stock-adjustment-smoke-password"
 2202:     part_number = f"SMOKE-STOCK-{uuid4().hex[:10]}"
 2203:     created_part_id: int | None = None
 2204:     user_id: int | None = None
 2205:
 2206:     def cleanup() -> None:
 2207:         with db_session() as db:
 2208:             if created_part_id is not None:
 2209:                 db.execute(
 2210:                     text(
 2211:                         "delete from audit_log "
 2212:                         "where entity_type = 'part' "
 2213:                         "and entity_id = :entity_id"
 2214:                     ),
 2215:                     {"entity_id": created_part_id},
 2216:                 )
 2217:                 db.execute(
 2218:                     text(
 2219:                         "delete from stock_movements "
 2220:                         "where part_id = :part_id"
 2221:                     ),
 2222:                     {"part_id": created_part_id},
 2223:                 )
 2224:                 db.execute(
 2225:                     text(
 2226:                         "delete from part_field_values "
 2227:                         "where part_id = :part_id"
 2228:                     ),
 2229:                     {"part_id": created_part_id},
 2230:                 )
 2231:                 db.execute(
 2232:                     text("delete from parts where id = :part_id"),
 2233:                     {"part_id": created_part_id},
 2234:                 )
 2235:             db.execute(
 2236:                 text(
 2237:                     "delete from sessions where user_id in "
 2238:                     "(select id from users where username = :username)"
 2239:                 ),
 2240:                 {"username": username},
 2241:             )
 2242:             db.execute(
 2243:                 text("delete from users where username = :username"),
 2244:                 {"username": username},
 2245:             )
 2246:             db.commit()
 2247:
 2248:     cleanup()
 2249:     client = TestClient(fastapi_app)
 2250:
 2251:     try:
 2252:         unauthenticated_adjustment = client.post(
 2253:             "/api/parts/1/quantity-adjustments",
 2254:             json={"operation": "add", "quantity": 1},
 2255:         )
 2256:         if unauthenticated_adjustment.status_code not in {401, 403}:
 2257:             fail(
 2258:                 "Quantity adjustment endpoint should require authentication, "
 2259:                 f"got {unauthenticated_adjustment.status_code}."
 2260:             )
 2261:         unauthenticated_history = client.get("/api/parts/1/movements")
 2262:         if unauthenticated_history.status_code not in {401, 403}:
 2263:             fail(
 2264:                 "Movement history endpoint should require authentication, "
 2265:                 f"got {unauthenticated_history.status_code}."
 2266:             )
 2267:
 2268:         with db_session() as db:
 2269:             user = create_user(
 2270:                 db,
 2271:                 username=username,
 2272:                 display_name="Stock Adjustment Smoke User",
 2273:                 password=password,
 2274:                 commit=True,
 2275:             )
 2276:             user_id = user.id
 2277:             session_token = create_session(
 2278:                 db,
 2279:                 user=user,
 2280:                 commit=True,
 2281:             )
 2282:             part_type_id = db.execute(
 2283:                 text("select id from part_types order by id limit 1")
 2284:             ).scalar()
 2285: ... excerpt truncated ...
```

Reservation smoke tests must use unique manifest-owned parts and reservations,
capture exact created IDs, and remove only those IDs. Required cases:

1. protected route rejection without a token;
2. create within availability;
3. reject exact oversubscription with no partial writes;
4. reject duplicate part items or verify normalization;
5. list and detail response shape;
6. cancellation releases exact counters;
7. second cancellation returns conflict and changes nothing;
8. quantity adjustment cannot reduce total below newly reserved stock;
9. active reservation blocks part deletion;
10. audit and movement rows are exact and linked;
11. complete cleanup leaves all pre-existing rows byte-for-byte unchanged.

Do not run those tests against persistent real inventory with broad delete
predicates.

## Frontend state and reusable inventory structures

Source presence:

| Potential module | Current state |
| --- | --- |
| project_route | Absent |
| project_schema | Absent |
| project_service | Absent |
| reservation_route | Absent |
| reservation_schema | Absent |
| reservation_service | Absent |

Frontend route state:

```text
   13: function AppRoutes() {
   14:   const {
   15:     user,
   16:     accountExists,
   17:     setupComplete,
   18:     isBooting
   19:   } = useAuth();
   20:
   21:   if (isBooting) {
   22:     return (
   23:       <main className="auth-page">
   24:         <div className="auth-window">
   25:           <section className="auth-form-panel">
   26:             <div className="brand-mark">P</div>
   27:             <p className="eyebrow">Starting Part Pilot</p>
   28:             <h2>Checking local session...</h2>
   29:           </section>
   30:         </div>
   31:       </main>
   32:     );
   33:   }
   34:
   35:   if (accountExists === false || !user) {
   36:     return <AuthScreen />;
   37:   }
   38:
   39:   if (setupComplete === false) {
   40:     return <SetupPreferencesScreen />;
   41:   }
   42:
   43:   return (
   44:     <Routes>
   45:       <Route element={<AppLayout />}>
   46:         <Route path="/" element={<Dashboard />} />
   47:         <Route path="/inventory" element={<Inventory />} />
   48:         <Route
   49:           path="/projects"
   50:           element={<PlaceholderPage title="Projects" />}
   51:         />
   52:         <Route
   53:           path="/reservations"
   54:           element={<PlaceholderPage title="Reservations" />}
   55:         />
   56:         <Route
   57:           path="/history"
   58:           element={<PlaceholderPage title="History" />}
   59:         />
   60:         <Route path="/part-manager" element={<PartManager />} />
   61:         <Route path="/settings" element={<Settings />} />
   62:       </Route>
   63:
   64:       <Route path="*" element={<Navigate to="/" replace />} />
   65:     </Routes>
   66:   );
   67: }
```

Placeholder component:

```text
    5: export function PlaceholderPage({ title }: PlaceholderPageProps) {
    6:   return (
    7:     <section className="page-stack">
    8:       <div className="page-header">
    9:         <p className="eyebrow">Placeholder</p>
   10:         <h1>{title}</h1>
   11:         <p>This screen is part of the V1 navigation, but not part of Phase 1 implementation.</p>
   12:       </div>
   13:     </section>
   14:   );
   15: }
```

Read-only route probes:

| Path | Status | Content type | Result |
| --- | --- | --- | --- |
| /api/health | 200 | application/json | Matches expected read-only response |
| /api/parts | 401 | application/json | Matches expected read-only response |
| /api/projects | 404 | application/json | Matches expected read-only response |
| /api/reservations | 404 | application/json | Matches expected read-only response |
| /projects | 200 | text/html; charset=utf-8 | Matches expected read-only response |
| /reservations | 200 | text/html; charset=utf-8 | Matches expected read-only response |

The existing parts client already supports server-backed search, stock status,
part type, location, limit and offset.

```text
   89: export function getParts(
   90:   token: string,
   91:   options?: {
   92:     partTypeId?: number;
   93:     locationId?: number;
   94:     search?: string;
   95:     stockStatus?: PartStockStatus;
   96:     sortBy?: PartSortBy;
   97:     sortDirection?: PartSortDirection;
   98:     availableSortBy?: PartSortBy;
   99:     availableSortDirection?: PartSortDirection;
  100:     outOfStockSortBy?: PartSortBy;
  101:     outOfStockSortDirection?: PartSortDirection;
  102:     limit?: number;
  103:     offset?: number;
  104:   }
  105: ): Promise<PartCollection> {
  106:   const parameters = new URLSearchParams();
  107:
  108:   if (options?.partTypeId) {
  109:     parameters.set(
  110:       "part_type_id",
  111:       String(options.partTypeId)
  112:     );
  113:   }
  114:
  115:   if (options?.locationId) {
  116:     parameters.set(
  117:       "location_id",
  118:       String(options.locationId)
  119:     );
  120:   }
  121:
  122:   // PATCH 217: typed backend universal-search option
  123:   const search = options?.search?.trim();
  124:   if (search) {
  125:     parameters.set("search", search);
  126:   }
  127:
  128:   // PATCH 232: PARTPILOT_STORED_PARTS_SERVER_SEARCH_V233
  129:   if (options?.stockStatus) {
  130:     parameters.set("stock_status", options.stockStatus);
  131:   }
  132:
  133:   // PATCH 269: PARTPILOT_STORED_PARTS_SORT_CLIENT_V270
  134:   if (options?.sortBy) {
  135:     parameters.set("sort_by", options.sortBy);
  136:   }
  137:   if (options?.sortDirection) {
  138:     parameters.set("sort_direction", options.sortDirection);
  139:   }
  140:
  141:   // PATCH 273: PARTPILOT_DYNAMIC_SECTION_SORT_CLIENT_V273
  142:   if (options?.availableSortBy) {
  143:     parameters.set("available_sort_by", options.availableSortBy);
  144:   }
  145:   if (options?.availableSortDirection) {
  146:     parameters.set(
  147:       "available_sort_direction",
  148:       options.availableSortDirection
  149:     );
  150:   }
  151:   if (options?.outOfStockSortBy) {
  152:     parameters.set(
  153:       "out_of_stock_sort_by",
  154:       options.outOfStockSortBy
  155:     );
  156:   }
  157:   if (options?.outOfStockSortDirection) {
  158:     parameters.set(
  159:       "out_of_stock_sort_direction",
  160:       options.outOfStockSortDirection
  161:     );
  162:   }
  163:
  164:   if (options?.limit !== undefined) {
  165:     parameters.set("limit", String(options.limit));
  166:   }
  167:
  168:   if (options?.offset !== undefined) {
  169:     parameters.set("offset", String(options.offset));
  170:   }
  171:
  172:   const query = parameters.toString();
  173:
  174:   return requestJson<PartCollection>(
  175:     `/parts${query ? `?${query}` : ""}`,
  176:     token
  177:   );
  178: }
```

Reusable signals:

```json
{
  "part_manager": {
    "dialog_patterns": true,
    "inventory_only_mode": true,
    "inventory_table": true,
    "selection_state": false,
    "server_search_marker": true
  },
  "parts_client": {
    "location_filter": true,
    "pagination": true,
    "part_type_filter": true,
    "server_search": true,
    "stock_status": true
  }
}
```

Do not embed the full Part Manager inside Reservations. Extract or build a
reservation-specific part picker that reuses the parts API contract and visual
table conventions while excluding create/edit/delete/restore/quantity-management
actions. The backend remains authoritative at submission time even when the
picker shows current availability.

## Exact live schema excerpts

### Project ORM

```text
  309: class Project(Base, TimestampMixin):
  310:     __tablename__ = "projects"
  311:     __table_args__ = (
  312:         CheckConstraint("status IN ('draft', 'reserved', 'consumed', 'cancelled')", name="ck_projects_status"),
  313:         CheckConstraint("created_by IN ('manual', 'ai', 'mcp', 'system')", name="ck_projects_created_by"),
  314:         CheckConstraint("estimated_total_value IS NULL OR estimated_total_value >= 0", name="ck_projects_estimated_total_value_nonnegative"),
  315:     )
  316:
  317:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
  318:     name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
  319:     description: Mapped[str | None] = mapped_column(Text, nullable=True)
  320:     status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
  321:     notes: Mapped[str | None] = mapped_column(Text, nullable=True)
  322:     created_by: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
  323:     estimated_total_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
  324:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
```

### ProjectItem ORM

```text
  327: class ProjectItem(Base, TimestampMixin):
  328:     __tablename__ = "project_items"
  329:     __table_args__ = (
  330:         CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
  331:         CheckConstraint("unit_price_snapshot IS NULL OR unit_price_snapshot >= 0", name="ck_project_items_unit_price_snapshot_nonnegative"),
  332:         Index("ix_project_items_project_part", "project_id", "part_id"),
  333:     )
  334:
  335:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
  336:     project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
  337:     part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
  338:     quantity: Mapped[int] = mapped_column(Integer, nullable=False)
  339:     unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
  340:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
  341:     note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Reservation ORM

```text
  344: class Reservation(Base, TimestampMixin):
  345:     __tablename__ = "reservations"
  346:     __table_args__ = (
  347:         CheckConstraint("status IN ('active', 'consumed', 'cancelled', 'expired')", name="ck_reservations_status"),
  348:         CheckConstraint("created_by IN ('manual', 'ai', 'mcp', 'system')", name="ck_reservations_created_by"),
  349:         CheckConstraint("estimated_reserved_value IS NULL OR estimated_reserved_value >= 0", name="ck_reservations_estimated_reserved_value_nonnegative"),
  350:     )
  351:
  352:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
  353:     project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
  354:     label: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
  355:     status: Mapped[str] = mapped_column(String(40), default="active", nullable=False, index=True)
  356:     notes: Mapped[str | None] = mapped_column(Text, nullable=True)
  357:     created_by: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
  358:     expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  359:     estimated_reserved_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
  360:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
```

### ReservationItem ORM

```text
  363: class ReservationItem(Base, TimestampMixin):
  364:     __tablename__ = "reservation_items"
  365:     __table_args__ = (
  366:         CheckConstraint("quantity > 0", name="ck_reservation_items_quantity_positive"),
  367:         CheckConstraint("unit_price_snapshot IS NULL OR unit_price_snapshot >= 0", name="ck_reservation_items_unit_price_snapshot_nonnegative"),
  368:         Index("ix_reservation_items_reservation_part", "reservation_id", "part_id"),
  369:     )
  370:
  371:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
  372:     reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
  373:     part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id", ondelete="SET NULL"), nullable=True, index=True)
  374:     quantity: Mapped[int] = mapped_column(Integer, nullable=False)
  375:     unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
  376:     currency_snapshot: Mapped[str | None] = mapped_column(String(12), nullable=True)
  377:     note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Foundation migration: projects

```text
  216:     op.create_table(
  217:         "projects",
  218:         sa.Column("id", sa.Integer(), primary_key=True),
  219:         sa.Column("name", sa.String(length=180), nullable=False),
  220:         sa.Column("description", sa.Text(), nullable=True),
  221:         sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
  222:         sa.Column("notes", sa.Text(), nullable=True),
  223:         sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
  224:         sa.Column("estimated_total_value", sa.Numeric(14, 4), nullable=True),
  225:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
  226:         *timestamps(),
  227:     )
  228:     op.create_index("ix_projects_name", "projects", ["name"])
  229:     op.create_index("ix_projects_status", "projects", ["status"])
```

### Foundation migration: project items

```text
  231:     op.create_table(
  232:         "project_items",
  233:         sa.Column("id", sa.Integer(), primary_key=True),
  234:         sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
  235:         sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
  236:         sa.Column("quantity", sa.Integer(), nullable=False),
  237:         sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
  238:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
  239:         sa.Column("note", sa.Text(), nullable=True),
  240:         *timestamps(),
  241:         sa.CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
  242:     )
  243:     op.create_index("ix_project_items_project_id", "project_items", ["project_id"])
  244:     op.create_index("ix_project_items_part_id", "project_items", ["part_id"])
```

### Foundation migration: reservations

```text
  246:     op.create_table(
  247:         "reservations",
  248:         sa.Column("id", sa.Integer(), primary_key=True),
  249:         sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
  250:         sa.Column("label", sa.String(length=180), nullable=False),
  251:         sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
  252:         sa.Column("notes", sa.Text(), nullable=True),
  253:         sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
  254:         sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True),
  255:         sa.Column("estimated_reserved_value", sa.Numeric(14, 4), nullable=True),
  256:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
  257:         *timestamps(),
  258:     )
  259:     op.create_index("ix_reservations_project_id", "reservations", ["project_id"])
  260:     op.create_index("ix_reservations_label", "reservations", ["label"])
  261:     op.create_index("ix_reservations_status", "reservations", ["status"])
```

### Foundation migration: reservation items

```text
  263:     op.create_table(
  264:         "reservation_items",
  265:         sa.Column("id", sa.Integer(), primary_key=True),
  266:         sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
  267:         sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
  268:         sa.Column("quantity", sa.Integer(), nullable=False),
  269:         sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
  270:         sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
  271:         sa.Column("note", sa.Text(), nullable=True),
  272:         *timestamps(),
  273:         sa.CheckConstraint("quantity > 0", name="ck_reservation_items_quantity_positive"),
  274:     )
  275:     op.create_index("ix_reservation_items_reservation_id", "reservation_items", ["reservation_id"])
  276:     op.create_index("ix_reservation_items_part_id", "reservation_items", ["part_id"])
```

## Recommended implementation order

1. **Contract-alignment migration and constants**
   - choose canonical reservation statuses;
   - align ORM/constants/live checks;
   - define movement snapshot/link fields;
   - add schema-only smoke coverage.
2. **Reservation schemas and service creation**
   - normalize items;
   - guarded stock updates;
   - transactional reservation/items/movements/audits.
3. **Protected list/detail/create/cancel API**
   - service-specific errors;
   - pagination and deterministic ordering;
   - exact protected-route smoke coverage.
4. **Consumption and explicit expiry service**
   - verify counter equations and idempotent transitions.
5. **Responsive Reservations workspace**
   - reservation-specific server-backed part picker;
   - no Projects implementation.
6. **Projects in a later independent boundary**
   - resolve project status vocabulary and lifecycle separately.

## Source hash allowlist

| Path | SHA-256 |
| --- | --- |
| backend/alembic/versions/0001_database_foundation.py | 82107d03f8ca60e3865a494bebb3071213857d49a0fcbe010b5aecebdb2f0807 |
| backend/alembic/versions/0002_schema_hardening.py | c3c70f7b9836d151431bd68b60454737b98a2db49315621d04dbba088186e8be |
| backend/app/api/routes/auth.py | 1518e3ce313f0c9d066b7f4d276ac78aa6f2e84c2a6252623ada04a12bb89ec6 |
| backend/app/api/routes/parts.py | 2501759a082a12e74dfab3ec9cc48be8e19bb426a96f0ef0ed3035fd2e3460b4 |
| backend/app/db/constants.py | 01464584d23710ba69bed518bb416c7adcd8bf8a6129079b4aa6cddb4f12cea8 |
| backend/app/db/smoke_test.py | 511b9f757f4129ef84846ead97c113760fb4a473ced62c34e78a736a0c4c6ad4 |
| backend/app/db/utils.py | 5e7fba07be860b3f8b5bc0f1da0ed2acc826ad44fa3fd844dbfbad6955f33278 |
| backend/app/main.py | 7d7b98a5301df1288eb12db16d0911331492603fc83be59b62e2479018c7c5b0 |
| backend/app/models/__init__.py | b4eb0d7e05406b7b598a85ac3216d042af5583d9260f8b14e757ec3cfab70617 |
| backend/app/models/core.py | 19d7ba1e6daa339f56e55eb2880b31e2c8d525e1965646b80414061aa443fbff |
| backend/app/schemas/parts.py | ef49c723706017ebbecbc8b8adccab5a3a6b1dbbab2d4fcde79f3c8ba9607589 |
| backend/app/services/auth.py | 389c44ac1f8ba48eef071c85e0c0b3cd6376988c730be39e0b3895d0ab501f90 |
| backend/app/services/parts.py | 34e448f514ed2f115cfc24b27a35667fbd7fdbec8472fd2d4101dcb0ed470998 |
| frontend/src/app/App.tsx | 38b2ad1f1215c36882a6e984ab0a96340832543742aa472b726e0a5efe6826c8 |
| frontend/src/app/AppLayout.tsx | a6dfac524d0f8d900f96e800fcf5deadb400aea231963f2ee5682fc264796bfe |
| frontend/src/pages/PartManager.css | b3c64207fa1c171e8770f46790cd693df41413f5fe5d242d52d4e5727bff10de |
| frontend/src/pages/PartManager.tsx | 1122bb8b9525775cc794b404875a49b5dc28a2ff9f89fb5df85607176ec793b9 |
| frontend/src/pages/PlaceholderPage.tsx | 79f45b149a8839b7d0fcb0c4c46e75202b270268da0185ef278925a64ec244a9 |
| frontend/src/services/partsClient.ts | 8dc0f4a07610807427e9bc56050ea84b76d504b5466ba377cdc4470f715fa43f |
| frontend/src/types/parts.ts | 755bb9817dd6e4363ddab11ae34896b68a22b32543832f09b5fbd64c67bca930 |

## Preservation proof

Before report creation:

- source hashes matched the exact allowlist;
- Git source and index were clean;
- live database snapshot digest was `d5e62c4351892a24f221756efdeba272891b09571d3de2677159eb034fd5f644`;
- container ID was `5f84a320d363`;
- all read-only route probes matched expected status and content type.

After report generation and before commit, the patch rechecks source hashes,
the complete live database row snapshot, container identity and read-only route
behaviour. After push, it repeats those checks and verifies local HEAD equals
`origin/main`.

## Diagnostic conclusion

Reservation implementation should begin only after aligning the reservation
status vocabulary and defining unambiguous movement snapshots. The existing
tables provide a usable base, but the live schema does not enforce the ORM
status checks, constants disagree with the ORM, and current movement fields
describe physical stock rather than reservation availability.

The safest first implementation slice is therefore a narrow schema/constants
contract patch, not an API patch and not a Projects patch.
