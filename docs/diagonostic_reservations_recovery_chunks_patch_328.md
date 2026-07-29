# Diagnostic — Reservations recovery chunks

<!-- PARTPILOT:DIAGONOSTIC_RESERVATIONS_RECOVERY_CHUNKS:V328 -->

Generated on 2026-07-29T19:03:46.526555+00:00.

## Result

**PASS — diagnostic only.**

No application source, build, deployment, reservation, fixture, or inventory
data was modified. Only this report is committed.

## Pending frontend source

```json
{
  "hashes": {
    "frontend/src/app/App.tsx": "9c5447280d0e4e715e50957cf5d9a39e9eaeb9fa819c3003d790a1c44b61db0a",
    "frontend/src/pages/Reservations.css": "015db71c1bf3610adc37609898187be4c20a6fe491ff1849f3b6ef5886b2494f",
    "frontend/src/pages/Reservations.tsx": "e85408675a39236e7373d351e87e1e1fe5ee5d08e1f9af84c3b0c002a925425f",
    "frontend/src/services/reservationsClient.ts": "fac88ed517914a8f9dd76ea686244d0645c8951cd43ad59256e144c6e2879a59",
    "frontend/src/types/reservations.ts": "732278dd52974488588e26e56feb95fc2a5d39e485fe7823cd8ca1d07e6b90dc"
  },
  "staged": [],
  "tracked": [
    "frontend/src/app/App.tsx"
  ],
  "untracked": [
    "frontend/src/pages/Reservations.css",
    "frontend/src/pages/Reservations.tsx",
    "frontend/src/services/reservationsClient.ts",
    "frontend/src/types/reservations.ts"
  ]
}
```

## Failed Patch 327

```json
{
  "log": "fixes/logs/327_reservations_recovery_diagnostic_20260730-002842.log",
  "log_sha256": "e29c0db7ca71e01be0f8b7daefc66ab28fb7c68fc2b0bd302b1ae19aa8cbb954",
  "patch": "fixes/327_diagnose_reservations_recovery_chunks.py",
  "patch_sha256": "0014cc8e69c48ad8e1fa3b83b6b2dda758aa9993bc9d94588b927811ecb6dd8c",
  "required_markers": [
    "FAILURE phase: preflight",
    "NameError: name 'ast' is not defined",
    "final HEAD: 5821378585c5c674324def6d80a7b5e606b071fa"
  ]
}
```

## Deployed assets

```json
{
  "assets": [
    {
      "checks": {
        "Create reservation": true,
        "Enter at least two characters": true,
        "Find parts": true,
        "New reservation": true,
        "PARTPILOT:RESERVATIONS_WORKSPACE:V322": true,
        "PARTPILOT:RESERVATIONS_WORKSPACE_STYLES:V322": false
      },
      "content_type": "text/javascript; charset=utf-8",
      "kind": "js",
      "path": "/assets/index-DjwIEXFs.js",
      "sha256": "0d464873736d7f075e3c8a99e42de75e3ea98e1f7658c3d9837038ace9fe778f",
      "size": 380799,
      "status": 200
    },
    {
      "checks": {
        "Create reservation": false,
        "Enter at least two characters": false,
        "Find parts": false,
        "New reservation": false,
        "PARTPILOT:RESERVATIONS_WORKSPACE:V322": false,
        "PARTPILOT:RESERVATIONS_WORKSPACE_STYLES:V322": false
      },
      "content_type": "text/css; charset=utf-8",
      "kind": "css",
      "path": "/assets/index-zSKiDglu.css",
      "sha256": "294fb4cf6bcf9ebccc01e971d5e8dcbb9aed215b39a20526cbf52fe76cf8a640",
      "size": 160444,
      "status": 200
    }
  ],
  "scripts": [
    "/assets/index-DjwIEXFs.js"
  ],
  "styles": [
    "/assets/index-zSKiDglu.css"
  ]
}
```

Finding: The production JavaScript contains the V322 marker.

## Reservation smoke test

```json
{
  "existing_data_safe_marker": false,
  "expected_active_total": false,
  "file_sha256": "e38e90f8d7fc2146579dc230c4a109105b2a512d5d4e7525e8a1b181bbbeefac",
  "function_end": 1341,
  "function_sha256": "a2a4a3bedaf7a9e2e0313c2a1f095d5cc7103b099b88e285735b5144baf58982",
  "function_start": 956,
  "relevant_lines": [
    "1006:                         \"delete from reservations \"",
    "1058:             (\"get\", \"/api/reservations\", None),",
    "1059:             (\"get\", \"/api/reservations/999999999\", None),",
    "1062:                 \"/api/reservations\",",
    "1083:                     \"where is_active = 1 order by id limit 1\"",
    "1108:                 total_quantity=5,",
    "1121:         created_ids: list[int] = []",
    "1127:                 \"/api/reservations\",",
    "1141:                     f\"POST /api/reservations returned \"",
    "1147:             created_ids.append(reservation_id)",
    "1149:         first_id, second_id = created_ids",
    "1152:             \"/api/reservations\",",
    "1154:             params={\"status\": \"active\", \"limit\": 1, \"offset\": 0},",
    "1158:                 \"GET /api/reservations first page returned \"",
    "1162:         first_items = first_page_json.get(\"reservations\", [])",
    "1164:             first_page_json.get(\"total\") != 2",
    "1165:             or first_page_json.get(\"limit\") != 1",
    "1170:                 \"Reservation list ordering or first-page metadata is \"",
    "1175:             \"/api/reservations\",",
    "1177:             params={\"status\": \"active\", \"limit\": 1, \"offset\": 1},",
    "1181:                 \"GET /api/reservations second page returned \"",
    "1185:         second_items = second_page_json.get(\"reservations\", [])",
    "1187:             second_page_json.get(\"total\") != 2",
    "1197:             f\"/api/reservations/{first_id}\",",
    "1202:                 \"GET /api/reservations/{id} returned \"",
    "1218:             f\"/api/reservations/{second_id + 999999}\",",
    "1228:             \"/api/reservations\",",
    "1243:             \"/api/reservations\",",
    "1264:                 \"reservations\": db.execute(",
    "1266:                         \"select count(*) from reservations \"",
    "1299:                         \"where event_type = 'reservation.created' \"",
    "1311:                 \"reservations\": 2,"
  ]
}
```

## Live database and inventory

```json
{
  "active_parts": 7,
  "alembic": "0006_reservation_contract",
  "audit_log": 36,
  "available_quantity": 142,
  "foreign_key_violations": 0,
  "integrity": "ok",
  "parts": 9,
  "reservation_items": 1,
  "reservation_rows": [
    {
      "created_at": "2026-07-29 17:53:16.159815",
      "id": 1,
      "label": "Weather Station",
      "project_id": null,
      "status": "active",
      "updated_at": "2026-07-29 17:53:16.159819"
    }
  ],
  "reservations": 1,
  "reserved_quantity": 2,
  "stock_movements": 5,
  "total_quantity": 144
}
```

## Chunked recovery plan

### Patch 329 — smoke test only

- Modify only `backend/app/db/smoke_test.py`.
- Make read/create totals relative to existing active reservations.
- Compile and run the complete smoke suite.
- Commit and push only the smoke-test file.
- Do not modify or stage pending frontend files.

### Patch 330 — CSS alignment only

- Modify only `frontend/src/pages/Reservations.css`.
- Keep all other pending frontend bytes unchanged.
- Build/deploy and verify via a durable CSS marker and UI route signal.
- Leave frontend source uncommitted for browser approval.

### Patch 331 — checkpoint and boundary recovery

- Run only after browser approval.
- Commit the approved frontend allowlist.
- Update durable checkpoint, roadmap, project memory and handoff.
- Push and verify local HEAD equals origin/main.

## Gate

Do not combine the smoke correction, CSS correction, and checkpoint commit.
