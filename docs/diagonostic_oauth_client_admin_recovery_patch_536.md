# Patch 536 Diagnostic — OAuth Client Administration Recovery

<!-- PARTPILOT:DIAGONOSTIC_OAUTH_CLIENT_ADMIN_RECOVERY:V536 -->

Generated: `2026-08-06 12:57:10Z`

## Verdict

**PASS — the repository and runtime are clean, and all three failure
causes are isolated. Patch 537 may retry only the corrected read-only
connected-client administration foundation.**

No application source, database row, credential, build, deployment,
README, or restore artifact was changed by this diagnostic recovery.

## Exact Git and deployment baseline

- Branch: `main`
- HEAD/origin: `bd40be7141bda0897ca5e60bc8cce2a8c1327edc`
- Subject: `Complete abandoned OAuth row cleanup`
- Working tree: clean
- Index: empty
- `git diff --check`: pass
- Deployment image: `sha256:41374c2471001cc9fcd38438e1a122ae19b0bd4dfc5330e2a1167e4098cdd602`
- Deployment: `running/healthy`, restart `0`
- Alembic: `0010_mcp_trusted_networks`
- Database SHA-256 at inspection: `49f60ee1c09d6ea123c0fddc31100019e7d226934a198dba2d391b1b342009e1`

## Restored application-source baseline

- `backend/app/schemas/app_settings.py`: `fbedc504006ac2f16e774fafcda50873fe02f7e062353e58320a56b482524e32`
- `backend/app/services/mcp_oauth.py`: `c99b36f95ae1c0a1f413a9905f7d85377449b256397df2aaa636008510b1af51`
- `backend/app/api/routes/app_settings.py`: `5cbf3933ce75349f85f64ed194843d035095ee5cec83da2adc4e2d16c7489824`
- `frontend/src/types/settings.ts`: `644472539b51827090a2d69ba11a14655b35f3194a5a623ef5b3d745084e484c`
- `frontend/src/services/settingsClient.ts`: `b377a503bbe7bd1476f5226570724de1c2b200109bc87c50b89f832002c03e42`
- `backend/app/db/mcp_oauth_admin_smoke_test.py`: absent, as expected
- No `V533` or `V534` administration marker exists in live source.

## Failure 1 — Patch 533

Patch 533 reached source write, then `git diff --check` rejected a new
blank line at the end of `backend/app/services/mcp_oauth.py`.

The exact transform was:

```python
932:         raise PatchFailure(
933:             "MCP OAuth service tail changed",
934:             phase="source transformation",
935:         )
936:     service = service.rstrip() + SERVICE_APPEND + "\n"
937:
938:     route = validate_text(
939:         ROUTE_REL,
940:         state.original_bytes[ROUTE_REL] or b"",
```

`SERVICE_APPEND` already carried trailing newlines, and the transform
added another newline. The persistent log records the EOF failure.

## Failure 2 — Patch 534

Patch 534 corrected the EOF transform:

```python
944:         raise PatchFailure(
945:             "MCP OAuth service tail changed",
946:             phase="source transformation",
947:         )
948:     service = service.rstrip() + SERVICE_APPEND.rstrip() + "\n"
949:
950:     route = validate_text(
951:         ROUTE_REL,
952:         state.original_bytes[ROUTE_REL] or b"",
```

It then failed before any write because its baseline validator searched
the Patch 533 persistent log for rollback phrases such as:

```python
1551:
1552:     failed_log_text = (
1553:         ROOT
1554:         / "fixes/logs/533_oauth_client_admin_foundation_20260806-123459.log"
1555:     ).read_text(encoding="utf-8", errors="replace")
1556:     for phrase in (
1557:         "git diff --check",
1558:         "backend/app/services/mcp_oauth.py:1260: new blank line at EOF.",
1559:         "backend/app/schemas/app_settings.py restored",
1560:         "backend/app/services/mcp_oauth.py restored",
1561:         "backend/app/db/mcp_oauth_admin_smoke_test.py removed",
1562:         "Final HEAD: bd40be7141bda0897ca5e60bc8cce2a8c1327edc",
1563:         "Final origin/main: bd40be7141bda0897ca5e60bc8cce2a8c1327edc",
1564:     ):
1565:         if phrase not in failed_log_text:
1566:             raise PatchFailure(
1567:                 f"Patch 533 failure evidence lacks {phrase!r}",
```

Those phrases were printed by `failure_report()` to terminal stdout:

```python
2211:     print(f"Failing command: {command}")
2212:     if stdout.strip():
2213:         print("Useful stdout:\n" + stdout.rstrip())
2214:     if stderr.strip():
2215:         print("Useful stderr:\n" + stderr.rstrip())
2216:     print(f"Rollback result: {rollback_result}")
2217:
2218:     final_status = state.run(
2219:         ["git", "status", "--short", "--branch"],
2220:         phase="failure reporting",
2221:         check=False,
```

They were never passed to `state.record()`, whose implementation is:

```python
791:         self.committed_head = ""
792:         self.last_command = ""
793:         self.last_stdout = ""
794:         self.last_stderr = ""
795:
796:     def record(self, message: str) -> None:
797:         self.log_path.parent.mkdir(parents=True, exist_ok=True)
798:         timestamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
799:         with self.log_path.open("a", encoding="utf-8") as handle:
800:             handle.write(f"[{timestamp}] {message}\n")
801:
```

Persistent logs cannot be required to contain terminal-only text.

## Failure 3 — Patch 535

Patch 535 correctly reached in-memory report generation, but its report
helper normalized only the end of each complete fragment:

```python
981:     oauth = state.oauth_snapshot
982:     lines: list[str] = []
983:
984:     def add(value: str = "") -> None:
985:         lines.append(value.rstrip())
986:
987:     add("# Patch 535 Diagnostic — OAuth Client Administration Recovery")
988:     add()
989:     add(f"<!-- {REPORT_MARKER} -->")
```

The five inserted source excerpts each contained one internal numbered
blank source line ending in `: ` after whole-fragment `rstrip()`.
Exact reproduced trailing-line count: `5`.
Affected fragments:
- `Patch 533 transform`
- `Patch 534 transform`
- `Patch 534 log expectation`
- `Patch 533 failure_report`
- `Patch 533 record method`

Patch 536 fixes this by normalizing every line independently:

```python
lines.extend(line.rstrip() for line in value.split("\n"))
```

This preserves code excerpts while removing trailing whitespace from
numbered blank lines before the final report validation.

## Current OAuth state — rotation-safe

- Client `9` — `Claude`, origin `https://claude.ai`, auth `client_secret_post`, token rows `3`, one family, active row `4`
- Client `13` — `ChatGPT`, origin `https://chatgpt.com`, auth `none`, token rows `1`, one family, active row `2`
- Authorization-code IDs: `[9, 10]`
- Consent IDs: `[8, 9]`
- Total token rows at inspection: `4`
- OAuth audit rows at inspection: `41`
- OAuth token refresh audits: `2`
- MCP enabled/read/write: `true/true/false`
- Hermes direct Bearer configuration: preserved

Historical token-row count, active token ID, database SHA, last-used
timestamps, and OAuth refresh-audit count are volatile and must not be
hard-coded by the implementation recovery.

The stable connected-client contract is:

- Exactly Claude client `9` and ChatGPT client `13`.
- Exactly one active consent per client.
- Exactly one token family per client.
- Exactly one non-revoked active token row per client.
- All token and consent scopes remain `mcp:read`.
- Resource URI remains `https://part.devansh.cc/mcp`.
- Rotation links remain within the same client and token family.
- No replay-detection state.

## Safe Patch 537 implementation plan

1. Require this Patch 536 diagnostic commit as exact HEAD/origin.
2. Validate the five restored source hashes and absence of
   `backend/app/db/mcp_oauth_admin_smoke_test.py`.
3. Validate Patch 533 only from persistent strings actually recorded:
   `git diff --check` and the EOF error.
4. Do not require terminal-only rollback or failure sentences from logs.
5. Build all six candidates in memory before writing.
6. Generate the service tail with:

   ```python
   service = service.rstrip() + SERVICE_APPEND.rstrip() + "\n"
   ```

7. Assert the service candidate ends with exactly one newline.
8. Compile all Python candidates and validate marker counts.
9. Validate OAuth connection semantics rather than volatile token totals,
   token IDs, database SHA, timestamps, or refresh-audit count.
10. Make copied-database smoke require a positive historical token count,
    one active token, and one active family per client.
11. Write exactly the six foundation files and run `git diff --check`
    before any build.
12. Build, run administration/OAuth/complete copied-database smoke,
    deploy, and verify the protected GET-only API and no-store headers.
13. Stage, commit, and push only the six foundation files.
14. Keep revocation out of Patch 537.

## Conclusion

Patch 537 may safely resume the read-only connected OAuth client
administration foundation using the corrected EOF transform, persistent
evidence rules, rotation-safe validation, and line-wise report hygiene.
