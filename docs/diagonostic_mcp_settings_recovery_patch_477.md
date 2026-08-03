# Patch 477 MCP Settings Recovery Diagnostic

Generated: `2026-08-03T06:21:48.005820+00:00`

## Result

Patch 476 rejected the live database because it inherited the historical
byte-level SHA-256 from Patch 474. The live database change is legitimate
authentication activity, not patch damage and not inventory drift.

The only logical changes relative to the exact Patch 474 stopped-database
backup are:

- `users.last_login_at`
- `users.updated_at`
- appended `sessions` rows

- Session `3` for user `1`, created `2026-08-03 05:50:50.263393`, expires `2026-09-02 05:50:50.261827`, token hash redacted.

All business tables, MCP settings, audit rows, inventory, Projects,
Reservations and OAuth tables match the Patch 474 baseline exactly.

## Git and deployment

- Branch: `main`
- HEAD: `7247ce6271ee62bd0ee56426b9ec01efd0458d84`
- origin/main: `7247ce6271ee62bd0ee56426b9ec01efd0458d84`
- Working tree and index: clean
- Deployment image: `sha256:a0561ba1c15b6f8dd91f301b681ecf12ac1b99c39e8097318838c0d9da4cb9ff`
- Health: `healthy`
- Restart count: `0`
- Started: `2026-08-03T00:03:28.792481718Z`

## Database

- Baseline SHA-256: `9aa77d72f2320a952221b3c1ea07bd0fa0881d04f76410f6065ee838771d21aa`
- Current SHA-256: `3e10b8d823c77043b62c40b779b9f88845134f54989c587bf5c8877b1253b922`
- Alembic: `0008_mcp_oauth`
- Integrity: `ok`
- Foreign-key violations: none
- Changed tables: `sessions, users`
- Previous last login: `2026-08-02 04:45:10.280861`
- Current last login: `2026-08-03 05:50:50.259889`
- Sessions: `2 -> 3`
- Counts: `{"audit_log": 103, "parts": 15, "project_items": 10, "projects": 7, "reservation_items": 14, "reservations": 9, "sessions": 3, "stock_movements": 32}`
- MCP settings: `{"mcp.enabled": {"value_json": "false", "value_text": null}, "mcp.read_tools_enabled": {"value_json": "true", "value_text": null}, "mcp.write_tools_enabled": {"value_json": "false", "value_text": null}}`
- OAuth rows: all zero

## Restore staging

- Entry count: `19`
- Fingerprint: `900cb94b4546e0dd1238b6a6f39c258baf17207ab79973e3815b44bafda5883e`
- Pending operations: `[]`

## Failure chain

1. Patch 473 reached source write and failed only because six generated files
   had an extra blank line at EOF. Rollback succeeded.
2. Patch 474 built and deployed the candidate, then its final live `/mcp`
   request omitted `Host: partpilot.example` and
   `X-Forwarded-Proto: https`. The gateway correctly returned HTTP 400.
   Rollback succeeded.
3. Patch 475 failed before state creation because it incorrectly required
   those new header strings to already exist in Patch 474.
4. Patch 476 removed that marker error but still inherited Patch 474's
   historical database SHA, so a legitimate login session caused a pre-write
   failure.

## Relevant source shape

### Patch 474 final MCP verification

```python
def verify_runtime(state: State) -> None:
    state.phase = "runtime verification"
    deployed = deployment_snapshot(state)
    if deployed["health"] != "healthy" or deployed["restart"] != "0":
        raise PatchFailure(
            f"Deployed container is unhealthy: {deployed}", phase=state.phase
        )
    if deployed["image"] == state.deployment_before["image"]:
        raise PatchFailure("Deployment image did not change", phase=state.phase)

    ready, _headers, _body = http_request("GET", "/api/ready")
    if ready != 200:
        raise PatchFailure(f"Readiness endpoint returned {ready}", phase=state.phase)
    unauthenticated, _headers, _body = http_request("GET", "/api/settings/mcp")
    if unauthenticated != 401:
        raise PatchFailure(
            f"Unauthenticated MCP settings GET returned {unauthenticated}",
            phase=state.phase,
        )
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "patch474", "version": "1"},
            },
        }
    ).encode("utf-8")
    mcp_status, challenge_headers, _body = http_request(
        "POST",
        "/mcp",
        body=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    if mcp_status != 401 or "oauth-protected-resource/mcp" not in challenge_headers.get(
        "www-authenticate", ""
    ):
        raise PatchFailure(
            f"MCP OAuth challenge is incorrect: {mcp_status} {challenge_headers}",
            phase=state.phase,
        )
    openapi_status, _headers, openapi_body = http_request("GET", "/openapi.json")
    if openapi_status != 200 or b'"/api/settings/mcp"' not in openapi_body:
        raise PatchFailure("MCP settings OpenAPI path is missing", phase=state.phase)
    verify_frontend_assets(state)

    if sha(DATABASE) != state.database_hash_before:
        raise PatchFailure("Live database bytes changed", phase=state.phase)
    validate_database(
        DATABASE, expected_rows=state.rows_before, phase=state.phase
    )
    if inventory_snapshot(DATABASE) != state.inventory_before:
        raise PatchFailure("Live inventory changed", phase=state.phase)
    if staging_snapshot() != state.staging_before:
        raise PatchFailure("Restore staging changed", phase=state.phase)
    if git(state, "rev-parse", "HEAD", phase=state.phase) != EXPECTED_HEAD:
        raise PatchFailure("HEAD changed during browser-test patch", phase=state.phase)
    if git(state, "rev-parse", "origin/main", phase=state.phase) != EXPECTED_HEAD:
        raise PatchFailure("origin/main changed during browser-test patch", phase=state.phase)
    assert_browser_test_status(state)


def cleanup_candidate_image(state: State) -> None:
    if state.candidate_created:
        state.run(
            ["docker", "image", "rm", "-f", state.candidate_tag],
            phase="cleanup",
            check=False,
        )
        state.candidate_created = False
```

### Patch 476 inherited recovery wrapper

```python
def load_base_module():
    if not BASE_SCRIPT.is_file() or sha256(BASE_SCRIPT) != BASE_SCRIPT_SHA256:
        raise RuntimeError("Exact Patch 474 script evidence mismatch")
    if not BASE_LOG.is_file() or sha256(BASE_LOG) != BASE_LOG_SHA256:
        raise RuntimeError("Exact Patch 474 failure log evidence mismatch")

    if (
        not PATCH_475_SCRIPT.is_file()
        or sha256(PATCH_475_SCRIPT) != PATCH_475_SCRIPT_SHA256
    ):
        raise RuntimeError("Exact consumed Patch 475 script evidence mismatch")

    source = BASE_SCRIPT.read_text(encoding="utf-8", errors="strict")
    required = (
        'PATCH_NUMBER = 474',
        'MCP OAuth challenge is incorrect',
        'if __name__ == "__main__":',
    )
    for marker in required:
        if marker not in source:
            raise RuntimeError(f"Patch 474 evidence marker missing: {marker}")
    if '"Host": "partpilot.example"' in source or '"X-Forwarded-Proto": "https"' in source:
        raise RuntimeError("Patch 474 no-header failure shape unexpectedly changed")

    spec = importlib.util.spec_from_file_location("partpilot_patch474_recovery_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Patch 474 implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

## Safe Patch 478 plan

1. Use Patch 474's exact target blobs and single-newline normalization.
2. Validate Patch 477's committed diagnostic report and the consumed Patch
   476 evidence.
3. At Patch 478 start, capture the current database SHA and complete logical
   row snapshot instead of requiring the historical Patch 474 SHA.
4. Permit pre-existing authentication-session drift, but freeze and preserve
   the exact current database bytes and rows from the start of Patch 478.
5. Keep the corrected HTTPS public-origin headers on the final `/mcp`
   verification request.
6. Build and test the isolated candidate, then back up, write, deploy and
   verify the same eight browser-test files.
7. Preserve all current sessions, inventory, Projects, Reservations, audit
   rows, OAuth state and restore staging.
8. Leave application source uncommitted and unstaged for browser approval.

No implementation should resume before this diagnostic patch passes and this
report is inspected.
