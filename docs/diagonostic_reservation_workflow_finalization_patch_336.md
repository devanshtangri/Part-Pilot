# Diagnostic — Reservation workflow finalization

<!-- PARTPILOT:DIAGONOSTIC_RESERVATION_WORKFLOW_FINALIZATION:V336 -->

Generated: 2026-07-30T07:06:50.530102+00:00

## Result

**PASS — diagnostic-only checkpoint.**

This patch inspected and documented the committed Chat 12 state. It did not
modify application source, migrations, deployment, reservations, projects,
fixtures, inventory, stock movements, audits, users or sessions.

Only this report is committed and pushed.

## Repository state

```json
{
  "branch": "main",
  "head": "4ff1e30fbdbb57e61c50fc86f924a6eea4c82c0d",
  "head_subject": "Complete Reservations foundation workspace",
  "index": "clean",
  "origin": "https://github.com/devanshtangri/Part-Pilot.git",
  "origin_main": "4ff1e30fbdbb57e61c50fc86f924a6eea4c82c0d",
  "recent_commits": [
    "4ff1e30 (HEAD -> main, origin/main) Complete Reservations foundation workspace",
    "ce4b9e6 Make reservation smoke existing-data-safe",
    "8369291 Diagnose Reservations recovery chunks",
    "5821378 Add reservation expiry workflow",
    "cb88a0e Diagnose reservation expiry checkpoint mismatch",
    "7a8f447 Add reservation consumption workflow",
    "8bdbaae Diagnose reservation consumption implementation",
    "cdbba89 Document reservation backend checkpoint"
  ],
  "status": "clean"
}
```

## Verified source hashes

```json
{
  "README.md": "f86576f8b2858b01c27699a0659bfd14e8b57d51f18694cc310b465209bb861e",
  "backend/app/api/routes/reservations.py": "9bee3e88d78229c9bbe22089f105cb0d570fba1eb37e717dc0bdfebde4ab9b59",
  "backend/app/db/seed.py": "6d03d88022c3a5ea1b9283ff0b1f7f4e9bafb17507d01c94f81a0284d172c5de",
  "backend/app/db/smoke_test.py": "8c43f5ae7fdd80dc125bc00fd066cdde55be61aa596bf219b7a383f1769bf28a",
  "backend/app/models/core.py": "8d80dd3fc1544d5ff7d7a7fc726d5da058f4726f37e95e19b8d8ff3e9a323679",
  "backend/app/schemas/reservations.py": "c44950d75fbb7d1a6b21b63f7bda55b4cc1187d7dda432922a17e72204d41abf",
  "backend/app/services/reservations.py": "4b26634dc8a954ee32101d8eadbfea0762d8a99e9d7feb1544e1238d43f7038b",
  "docs/Chat_12_Reservations_Foundation_Handoff.md": "51630891942bb2c217fde5036298a73935ea5ec7aeb88dcfedc183cb63aa2c75",
  "docs/Checkpoint.md": "8bf76455073696ba9e074ef87175b08eb62fa819a636c6d0bfc7810d230da7b4",
  "docs/Implementation_Roadmap.md": "4f121ba8db3f3de700fba11c3cface4cce55351d94f4bd57f627e409856f2d34",
  "docs/Part_Pilot_Project_Memory.txt": "bc7e7f8769073cbd95884db8d7f8fef38dad4dbaa8f1da8701c3a59c943f8f77",
  "docs/diagonostic_reservations_recovery_chunks_patch_328.md": "eb825fc4313abe350a8af968691329273ed7ed97a6ae172d3f225adfa7726868",
  "frontend/src/app/App.tsx": "9c5447280d0e4e715e50957cf5d9a39e9eaeb9fa819c3003d790a1c44b61db0a",
  "frontend/src/pages/Reservations.css": "519636d9b7563ad856f99fa747d9e9d69ba1fe87b4b07deb33020a5d86b1f4bc",
  "frontend/src/pages/Reservations.tsx": "e85408675a39236e7373d351e87e1e1fe5ee5d08e1f9af84c3b0c002a925425f",
  "frontend/src/services/reservationsClient.ts": "fac88ed517914a8f9dd76ea686244d0645c8951cd43ad59256e144c6e2879a59",
  "frontend/src/types/reservations.ts": "732278dd52974488588e26e56feb95fc2a5d39e485fe7823cd8ca1d07e6b90dc"
}
```

## Deployment and Alembic

```json
{
  "alembic_current_stderr": "INFO  [alembic.runtime.migration] Context impl SQLiteImpl.\nINFO  [alembic.runtime.migration] Will assume non-transactional DDL.",
  "alembic_current_stdout": "0006_reservation_contract (head)",
  "alembic_heads_stderr": "",
  "alembic_heads_stdout": "0006_reservation_contract (head)",
  "compose_ps": "NAME        IMAGE                 COMMAND                  SERVICE     CREATED             STATUS             PORTS\npartpilot   partpilot-partpilot   \"sh -c 'uvicorn app.\u2026\"   partpilot   About an hour ago   Up About an hour   0.0.0.0:7890->8000/tcp, [::]:7890->8000/tcp",
  "health_body": "{\"status\":\"ok\",\"app\":\"Part Pilot\",\"environment\":\"development\"}",
  "health_status": "200",
  "reservations_route_bytes": 395,
  "reservations_route_has_root": true,
  "reservations_route_status": "200",
  "unauthenticated_reservations_status": "401"
}
```

## Live database preservation snapshot

```json
{
  "alembic": "0006_reservation_contract",
  "counts": {
    "audit_log": 36,
    "parts": 9,
    "project_items": 0,
    "projects": 0,
    "reservation_items": 1,
    "reservations": 1,
    "sessions": 5,
    "stock_movements": 5,
    "users": 1
  },
  "db_path": "/projects/Part Pilot/data/partpilot.db",
  "db_size": 565248,
  "foreign_key_violations": [],
  "integrity": "ok",
  "inventory": {
    "active_parts": 7,
    "available_quantity": 150,
    "part_rows": 9,
    "reserved_quantity": 2,
    "total_quantity": 152
  },
  "projects": [],
  "reservation_audits": [
    {
      "actor_type": "user",
      "actor_user_id": 1,
      "created_at": "2026-07-29 17:53:16.167598",
      "entity_id": 1,
      "event_type": "reservation.created",
      "id": 36,
      "summary": "Created reservation Weather Station with 1 parts"
    }
  ],
  "reservation_items": [
    {
      "created_at": "2026-07-29 17:53:16.164588",
      "currency_snapshot": "INR",
      "id": 1,
      "note": null,
      "part_id": 7,
      "quantity": 2,
      "reservation_id": 1,
      "unit_price_snapshot": 26,
      "updated_at": "2026-07-29 17:53:16.164591"
    }
  ],
  "reservation_movements": [
    {
      "actor_user_id": 1,
      "available_quantity_after": 20,
      "available_quantity_before": 22,
      "created_at": "2026-07-29 17:53:16.165927",
      "id": 5,
      "movement_type": "reserve",
      "part_id": 7,
      "quantity_after": 22,
      "quantity_before": 22,
      "quantity_delta": 0,
      "reason": "Reserved for Weather Station",
      "reservation_id": 1,
      "reserved_quantity_after": 2,
      "reserved_quantity_before": 0,
      "source": "manual"
    }
  ],
  "reservations": [
    {
      "created_at": "2026-07-29 17:53:16.159815",
      "created_by": "manual",
      "currency_snapshot": "INR",
      "estimated_reserved_value": 52,
      "expiry_at": "2026-07-31 17:52:00.000000",
      "id": 1,
      "label": "Weather Station",
      "notes": null,
      "project_id": null,
      "status": "active",
      "updated_at": "2026-07-29 17:53:16.159819"
    }
  ]
}
```

The live **Weather Station** reservation is user data. Its reservation row,
item, reserve movement and audit record are explicitly captured above and must
remain untouched by automated cleanup.

## Exact source shape

### Reservation service definitions

```json
[
  {
    "end": 41,
    "kind": "ClassDef",
    "name": "ReservationConflictError",
    "start": 40
  },
  {
    "end": 45,
    "kind": "ClassDef",
    "name": "ReservationValidationError",
    "start": 44
  },
  {
    "end": 52,
    "kind": "ClassDef",
    "name": "_NormalisedReservationItem",
    "start": 49
  },
  {
    "end": 88,
    "kind": "FunctionDef",
    "name": "_normalise_items",
    "start": 55
  },
  {
    "end": 103,
    "kind": "FunctionDef",
    "name": "_normalise_expiry",
    "start": 91
  },
  {
    "end": 110,
    "kind": "FunctionDef",
    "name": "_currency_snapshot",
    "start": 106
  },
  {
    "end": 148,
    "kind": "FunctionDef",
    "name": "_serialise_created_reservation",
    "start": 113
  },
  {
    "end": 376,
    "kind": "FunctionDef",
    "name": "create_reservation",
    "start": 151
  },
  {
    "end": 380,
    "kind": "ClassDef",
    "name": "ReservationNotFoundError",
    "start": 379
  },
  {
    "end": 462,
    "kind": "FunctionDef",
    "name": "_serialise_reservation",
    "start": 383
  },
  {
    "end": 472,
    "kind": "FunctionDef",
    "name": "get_reservation",
    "start": 465
  },
  {
    "end": 525,
    "kind": "FunctionDef",
    "name": "list_reservations",
    "start": 475
  },
  {
    "end": 743,
    "kind": "FunctionDef",
    "name": "cancel_reservation",
    "start": 529
  },
  {
    "end": 986,
    "kind": "FunctionDef",
    "name": "consume_reservation",
    "start": 747
  },
  {
    "end": 1216,
    "kind": "FunctionDef",
    "name": "expire_reservation",
    "start": 990
  }
]
```

### Reservation route definitions

```json
[
  {
    "end": 56,
    "kind": "FunctionDef",
    "name": "read_reservations",
    "start": 38
  },
  {
    "end": 75,
    "kind": "FunctionDef",
    "name": "read_reservation",
    "start": 63
  },
  {
    "end": 104,
    "kind": "FunctionDef",
    "name": "create_reservation_record",
    "start": 83
  },
  {
    "end": 133,
    "kind": "FunctionDef",
    "name": "cancel_reservation_record",
    "start": 112
  },
  {
    "end": 162,
    "kind": "FunctionDef",
    "name": "consume_reservation_record",
    "start": 141
  },
  {
    "end": 191,
    "kind": "FunctionDef",
    "name": "expire_reservation_record",
    "start": 170
  }
]
```

### Reservation schema definitions

```json
[
  {
    "end": 37,
    "kind": "ClassDef",
    "name": "ReservationItemCreateRequest",
    "start": 24
  },
  {
    "end": 80,
    "kind": "ClassDef",
    "name": "ReservationCreateRequest",
    "start": 40
  },
  {
    "end": 95,
    "kind": "ClassDef",
    "name": "ReservationItemResponse",
    "start": 83
  },
  {
    "end": 110,
    "kind": "ClassDef",
    "name": "ReservationResponse",
    "start": 98
  },
  {
    "end": 117,
    "kind": "ClassDef",
    "name": "ReservationCollectionResponse",
    "start": 113
  }
]
```

### Relevant frontend lines

```json
[
  "44:  { value: \"cancelled\", label: \"Cancelled\" },",
  "477:      cancel: \"Cancel\",",
  "481:    const confirmed = window.confirm(",
  "535:          <span>Active on page</span>",
  "539:          <span>Due on page</span>",
  "543:          <span>Reserved units on page</span>",
  "581:            placeholder=\"Search this page\"",
  "622:          <div className=\"reservations-list\" aria-live=\"polite\">",
  "769:                  <dt>Linked project</dt>",
  "834:                      : \"Consume reservation\"}",
  "842:                    {actionName === \"cancel\" ? \"Cancelling\u2026\" : \"Cancel\"}",
  "851:                      {actionName === \"expire\" ? \"Expiring\u2026\" : \"Mark expired\"}",
  "951:                <div className=\"reservation-part-results\" aria-live=\"polite\">",
  "1056:                  Cancel"
]
```

### Relevant route lines

```json
[
  "19:    cancel_reservation,",
  "20:    consume_reservation,",
  "21:    expire_reservation,",
  "22:    create_reservation,",
  "23:    get_reservation,",
  "24:    list_reservations,",
  "34:@router.get(",
  "51:    return list_reservations(",
  "59:@router.get(",
  "70:        return get_reservation(db, reservation_id)",
  "78:@router.post(",
  "83:def create_reservation_record(",
  "89:        return create_reservation(",
  "108:@router.post(",
  "112:def cancel_reservation_record(",
  "118:        return cancel_reservation(",
  "137:@router.post(",
  "141:def consume_reservation_record(",
  "147:        return consume_reservation(",
  "166:@router.post(",
  "170:def expire_reservation_record(",
  "176:        return expire_reservation("
]
```

### Relevant service lines

```json
[
  "123:        created_by=reservation.created_by,",
  "127:        created_at=reservation.created_at,",
  "199:        project_id=None,",
  "266:            movement = StockMovement(",
  "312:                event_type=\"reservation.created\",",
  "418:        created_by=reservation.created_by,",
  "422:        created_at=reservation.created_at,",
  "622:            movement = StockMovement(",
  "686:                event_type=\"reservation.cancelled\",",
  "859:            movement = StockMovement(",
  "927:                event_type=\"reservation.consumed\",",
  "1099:            movement = StockMovement(",
  "1160:                event_type=\"reservation.expired\","
]
```

### Expiry-setting seed lines

```json
[
  "59:    \"reservations.expiry.mode\": {\"value_json\": \"none\", \"value_text\": \"none\"},",
  "60:    \"reservations.expiry.default_days\": {\"value_json\": None, \"value_text\": None},"
]
```

## Gap matrix

```json
{
  "create_schema_accepts_project_id": false,
  "create_service_forces_project_none": true,
  "expiry_seed_settings_present": true,
  "expiry_settings_used_by_reservation_service": false,
  "extend_client_present": false,
  "extend_route_present": false,
  "extend_ui_present": false,
  "history_route_is_placeholder": true,
  "lifecycle_success_feedback_present": false,
  "project_backend_files_present": {
    "backend/app/api/routes/projects.py": false,
    "backend/app/schemas/projects.py": false,
    "backend/app/services/projects.py": false,
    "frontend/src/pages/Projects.tsx": false,
    "frontend/src/services/projectsClient.ts": false
  },
  "projects_route_is_placeholder": true,
  "reservation_history_client_present": false,
  "reservation_history_endpoint_present": false,
  "reservation_history_ui_present": false,
  "search_is_loaded_page_only": true,
  "summary_is_page_scoped": true,
  "window_confirm_used": true
}
```

## Findings

1. Projects are still a placeholder and have no service, schema, API or frontend client. Reservation creation therefore cannot safely link a project yet; the current service explicitly stores `project_id=None`.
2. Reservation lifecycle movements and audit records already exist, including the live Weather Station reserve movement and `reservation.created` audit, but no reservation-scoped history read API or history presentation exists.
3. The global `/history` route is still a placeholder. A narrow reservation activity panel can be delivered without prematurely building the full History workspace.
4. The durable product checklist names Extend and Open project actions, but neither action has a route, client method or UI implementation. Open project must remain deferred until Projects has a real route and contract.
5. Expiry default settings are seeded but are not consumed by the reservation creation service or Reservations UI.
6. Current list search filters only the loaded page, and the summary cards explicitly report page-scoped counts. This is honest UI, but not server-wide search or aggregation.
7. Lifecycle confirmation still uses `window.confirm`; there is no durable success message after create/cancel/consume/expire. Accessibility and action-feedback finalisation should be a later frontend-only browser-tested slice.

## Safe implementation plan

```json
[
  {
    "scope": "Add a read-only authenticated reservation activity response assembled from reservation-linked stock movements and audit events. Do not alter lifecycle writes, schema, migrations, projects or frontend.",
    "slice": "A \u2014 reservation activity backend",
    "validation": "Compile backend, run complete smoke suite, add isolated existing-data-safe API coverage, verify Weather Station and all inventory aggregates are unchanged."
  },
  {
    "scope": "Present the backend activity in reservation detail with loading, empty and error states. Keep the global History page out of scope.",
    "slice": "B \u2014 reservation activity frontend",
    "validation": "Build/deploy, verify protected APIs and SPA markers, then browser-test before committing."
  },
  {
    "scope": "Add a guarded active-reservation expiry update/extension contract with audit coverage. Keep default expiry settings and frontend controls separate.",
    "slice": "C \u2014 expiry extension backend",
    "validation": "Use manifest-owned fixtures only and prove no stock, reservation status or Weather Station data changes."
  },
  {
    "scope": "Replace fragile confirmation/feedback behaviour with an accessible in-app confirmation and durable success status; preserve all lifecycle semantics.",
    "slice": "D \u2014 action feedback and accessibility",
    "validation": "Frontend-only browser test with complete mock values and explicit cleanup instructions."
  },
  {
    "scope": "Run a separate Projects architecture diagnostic before enabling reservation project linkage or Open project. Do not invent linkage against the current placeholder route.",
    "slice": "E \u2014 Projects boundary",
    "validation": "Inspect existing project tables, statuses and reservation FK without modifying user data."
  }
]
```

## Patch 337 recommendation

Implement **Slice A only: reservation activity backend**.

The next implementation should add an authenticated, read-only,
reservation-scoped activity contract sourced from existing reservation-linked
stock movements and reservation audit events. It should not modify the
reservation lifecycle, database schema, Alembic head, Projects placeholder,
frontend source or expiry settings.

The implementation and its smoke coverage should be split if source shape or
test complexity becomes uncertain. Every fixture must be unique and cleanup
must target only exact owned IDs.

## Gates

- Preserve the Weather Station reservation and all related rows exactly.
- Preserve total, reserved and available inventory aggregates.
- Preserve current deployment until an application patch is intentionally
  built and deployed.
- Do not implement project linkage against the placeholder Projects route.
- Do not combine backend history, frontend presentation, expiry extension,
  accessibility and documentation checkpoint work in one patch.
