# Patch 525 Diagnostic — OAuth Checkpoint Recovery

<!-- PARTPILOT:DIAGONOSTIC_OAUTH_CHECKPOINT_RECOVERY:V525 -->

Generated: `2026-08-06 07:59:34Z`

## Verdict

**PASS — the approved application source is sound and all five failures
were defects in checkpoint/diagnostic validation scripts.**

Patches 520 through 524 all failed before staging, report writing,
committing, pushing, building, deploying, or changing database rows.
The two browser-approved OAuth source files remain exact, modified, and
unstaged. The Git index remains empty.

## Exact failure chain

1. Patch 520 searched the V519 smoke source for a literal CSP fragment
   that the smoke test constructs semantically instead.
2. Patch 521 corrected that source check but required terminal-only failure
   text from a log that records announcements and commands, not the
   `failure_report()` terminal output.
3. Patch 522 reached diagnostic report generation, then rejected trailing
   whitespace in dynamically inserted lines before normalizing them.
4. Patch 523 normalized report lines, then searched the raw wrapped report
   for a phrase spanning two Markdown lines.
5. Patch 524 attempted to diagnose Patch 523 with an over-escaped source
   string: it searched for four backslashes before `n` where the exact
   Patch 523 source contains two characters, backslash plus `n`.

Patch 525 does not inherit or transform those marker assertions. It uses
exact file hashes, exact Git state, semantic runtime checks, optional
source excerpts, and line-by-line report construction.

## Exact Git and deployment baseline

- Branch: `main`
- Baseline HEAD/origin: `a31aadf084066d7e0bf31e883f0d55150d8b38f4`
- Baseline subject: `Complete Chat 18 MCP authentication boundary`
- Origin: `git@github.com:devanshtangri/Part-Pilot.git`
- Git index: empty
- Pending application files: exactly two, modified and unstaged
- Deployed image: `sha256:a2954d8cd2f84cbd283d77d8679bc881e14f6896d0e3df737bb5e178dabbba44`
- Compose image: `partpilot-partpilot`
- Container: `running/healthy`, restart `0`
- Container start: `2026-08-06T03:36:01.241887699Z`
- Alembic head: `0010_mcp_trusted_networks`
- Database SHA-256 at inspection: `0223520181201b321750a0887527161b724aebe5cf6ff92e56181d9091210c6f`

## Pending browser-approved source

- `backend/app/api/routes/mcp_oauth.py` — SHA-256 `09ae198f1d1df39dadf22b69cfadb794dc84ad8df88b48fa75d502d244b1cf3c`, diff `+422/-79`
- `backend/app/db/mcp_oauth_http_smoke_test.py` — SHA-256 `b0525f05880d7e0428daeea2e3f12656ddcc7f8019316e5d5d2a96fd7a870aa2`, diff `+366/-66`

These files must remain unstaged during this documentation-only patch.

## Exact Patch 518–524 evidence manifest

- `fixes/518_complete_oauth_connector_browser_workflow.py`: `435360becf10c7263b45670b0d6853f6d852f10fff3c32232d84bec34239eb0a`
- `fixes/519_allow_validated_oauth_callback_navigation.py`: `23da9b71882ff23c06b9fab3d5477daf6c2677e0b26c1d9f0b7311d34727765c`
- `fixes/520_checkpoint_oauth_connector_workflow.py`: `645b6a72ea40a229dea7642ddd0cab02952c5e056315b6540aa99b7395d7b495`
- `fixes/521_recover_oauth_connector_checkpoint.py`: `e5738f7139782cefa5e7c6c8a2391ce78897f1e1cd5f7c9fc4ed766ffde20796`
- `fixes/522_diagnose_oauth_connector_checkpoint_failures.py`: `e81ee14520dbc5b23530f4e366fd9a810fbb23fc0d4f9a7412151ce2e3416437`
- `fixes/523_recover_oauth_connector_checkpoint_diagnostic.py`: `7f622cd2ae2bfae556f29cdb31a00230be5b875db50813571756fe782b367f45`
- `fixes/524_recover_oauth_connector_checkpoint_diagnostic_marker.py`: `9a426f6a76cee057799c3328d5c3bf55b922e629dc563d17d071dd26e5968896`
- `fixes/logs/518_oauth_connector_browser_workflow_20260805-184821.log`: `14ecb9042467044f0d4be3c52a3504b5c6604f7dc183f947aa6767828c9fe4e1`
- `fixes/logs/519_oauth_callback_csp_fix_20260806-033454.log`: `7c0a632e9b3ab1860e5d888e784f5111a224e2c47db02cb96eb8945e50d5d45f`
- `fixes/logs/520_oauth_connector_checkpoint_20260806-044409.log`: `8c826ab317000bcc2a4033480b87f0930692dd368230d01280e4b7e14f7aaee1`
- `fixes/logs/521_oauth_connector_checkpoint_recovery_20260806-045048.log`: `1a66af13a5d10e67b83322b4a4da9618c36f7f290ecc3dbfa13644791116533b`
- `fixes/logs/522_oauth_connector_checkpoint_diagnostic_20260806-051106.log`: `2c546274d274d0af24d1967c336c7d455971ad86843183bbd12918c5c6ddb1f6`
- `fixes/logs/523_oauth_connector_checkpoint_diagnostic_recovery_20260806-051755.log`: `142d75776e6685bbe7ff98ea77a53996cd47e0508cea6f006158fac84e03579d`
- `fixes/logs/524_oauth_connector_checkpoint_diagnostic_recovery_20260806-052617.log`: `0ab8224eef01b36123a20e619fe0aaad4ffe71fcdebe44238606a6f0cb36ed35`

## Patch 520 invalid source-marker check

```text
0681:         "Denying...",
0682:         "script-src 'nonce-",
0683:         "validated_redirect = validate_redirect_uri(form_action_redirect_uri)",
0684:     )
0685:     smoke_markers = (
0686:         "PARTPILOT:MCP_OAUTH_HTTP_SMOKE:V519",
0687:         "form_action_origin=callback_origin",
0688:         "form-action 'self'",
0689:         "validated callback-origin form-action",
0690:         "PartPilot-OAuth-Smoke-518!",
0691:         "assert_shell(",
0692:     )
0693:     for marker in route_markers:
0694:         if marker not in route:
0695:             raise PatchFailure(
```

## Patch 521 impossible log-marker check

```text
0756:                 phase="evidence validation",
0757:             )
0758:
0759:     log520 = (
0760:         ROOT / "fixes/logs/520_oauth_connector_checkpoint_20260806-044409.log"
0761:     ).read_text(encoding="utf-8", errors="replace")
0762:     for marker in (
0763:         "Patch 520 failed.",
0764:         "Phase: approved source validation",
0765:         'Approved smoke marker missing: "form-action \'self\'"',
0766:         "Rollback result: no Git writes had occurred; exact browser-approved source preserved",
0767:         EXPECTED_HEAD,
0768:     ):
0769:         if marker not in log520:
0770:             raise PatchFailure(
```

## Patch 522 pre-normalization whitespace check

```text
1093:     trailing = [
1094:         index + 1
1095:         for index, line in enumerate(lines)
1096:         if line.rstrip() != line
1097:     ]
1098:     if trailing:
1099:         raise PatchFailure(
1100:             f"Generated report contains trailing whitespace: {trailing[:20]}",
1101:             phase="report generation",
1102:         )
1103:     if not report.endswith("\n"):
1104:         report += "\n"
1105:     encoded = report.encode("utf-8")
1106:     for marker in (
1107:         "# Patch 522 Diagnostic — OAuth Connector Checkpoint Failures",
```

## Patch 523 wrapped report-marker check

```text
1183:         "PARTPILOT:DIAGONOSTIC_OAUTH_CONNECTOR_CHECKPOINT:V523",
1184:         "checkpoint-script validation defects",
1185:         "Patch 521 impossible log-marker assertion",
1186:         "Patch 522 trailing-whitespace guard",
1187:         "strips trailing whitespace from every line",
1188:         "Safe Patch 524 checkpoint plan",
1189:         "**Not** require terminal-only failure text",
1190:         "MCP write tools remain disabled",
1191:     ):
1192:         if marker not in report:
1193:             raise PatchFailure(
1194:                 f"Generated report lacks marker: {marker!r}",
1195:                 phase="report generation",
1196:             )
1197:     return encoded
```

## Patch 524 over-escaped source-shape check

```text
0680:         ),
0681:         "patch523_wrapped_write_marker": validate_marker_count(
0682:             patch523,
0683:             '"MCP write tools remain disabled",',
0684:             1,
0685:             label="Patch 523",
0686:         ),
0687:         "patch523_report_sentence_wrap": validate_marker_count(
0688:             patch523,
0689:             "The successful Claude and ChatGPT token rows must be preserved. MCP write tools\\nremain disabled.",
0690:             1,
0691:             label="Patch 523",
0692:         ),
0693:         "patch523_whitespace_compaction": validate_marker_count(
0694:             patch523,
```

## Execution-log facts

- Patch 520: terminal failure banner present in execution log: `false`
- Patch 520: report-write/staging step reached: `false`
- Patch 521: terminal failure banner present in execution log: `false`
- Patch 521: report-write/staging step reached: `false`
- Patch 522: terminal failure banner present in execution log: `false`
- Patch 522: report-write/staging step reached: `false`
- Patch 523: terminal failure banner present in execution log: `false`
- Patch 523: report-write/staging step reached: `false`
- Patch 524: terminal failure banner present in execution log: `false`
- Patch 524: report-write/staging step reached: `false`

The failure banners shown in the terminal were not persisted by the
scripts' `State.record()` log writer. None of the five logs reached a
report-write or staging step.

### Tail of Patch 520 execution log

```text
[04:44:15Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:44:15Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:44:15Z] $ git status --short --branch
rc=0
## main...origin/main
 M backend/app/api/routes/mcp_oauth.py
 M backend/app/db/mcp_oauth_http_smoke_test.py

[04:44:15Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:44:15Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4
```

### Tail of Patch 521 execution log

```text
[04:50:55Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:50:55Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:50:55Z] $ git status --short --branch
rc=0
## main...origin/main
 M backend/app/api/routes/mcp_oauth.py
 M backend/app/db/mcp_oauth_http_smoke_test.py

[04:50:55Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[04:50:55Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4
```

### Tail of Patch 522 execution log

```text
[05:11:14Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:11:14Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:11:14Z] $ git status --short --branch
rc=0
## main...origin/main
 M backend/app/api/routes/mcp_oauth.py
 M backend/app/db/mcp_oauth_http_smoke_test.py

[05:11:14Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:11:14Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4
```

### Tail of Patch 523 execution log

```text
[05:18:02Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:18:02Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:18:02Z] $ git status --short --branch
rc=0
## main...origin/main
 M backend/app/api/routes/mcp_oauth.py
 M backend/app/db/mcp_oauth_http_smoke_test.py

[05:18:02Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:18:02Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4
```

### Tail of Patch 524 execution log

```text
[05:26:23Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:26:23Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:26:23Z] $ git status --short --branch
rc=0
## main...origin/main
 M backend/app/api/routes/mcp_oauth.py
 M backend/app/db/mcp_oauth_http_smoke_test.py

[05:26:23Z] $ git rev-parse HEAD
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4

[05:26:23Z] $ git rev-parse origin/main
rc=0
a31aadf084066d7e0bf31e883f0d55150d8b38f4
```

## Live application and MCP state

- Parts: `15`
- Projects: `7`
- Reservations: `9`
- Stock movements: `32`
- Audit rows at inspection: `167`
- App settings: `17`
- Direct-auth rows: `1`
- OAuth clients at inspection: `17`
- OAuth authorization codes at inspection: `10`
- OAuth consents at inspection: `9`
- OAuth tokens: `2`
- MCP enabled/read/write: `true/true/false`
- Direct mode: `bearer_key`
- Direct key prefix only: `pp_mcp_key_ee4mnPTlR`
- Direct key last used: `2026-08-06 07:54:58.635429`
- Instance secret: present, mode `0600`, exact expected SHA-256
- Restore staging: present, no pending operation

### Successful read-only OAuth tokens

- Token `1`: client `Claude`, scopes `["mcp:read"]`, resource `https://part.devansh.cc/mcp`, revoked `false`, last used `2026-08-06 03:40:08.569871`
- Token `2`: client `ChatGPT`, scopes `["mcp:read"]`, resource `https://part.devansh.cc/mcp`, revoked `false`, last used `2026-08-06 03:45:36.772468`

Claude and ChatGPT remain connected with `mcp:read` only. Hermes
continues using the direct Bearer credential. MCP write authorization
remains disabled.

## Safe Patch 526 checkpoint plan

Patch 526 may perform the two-file OAuth checkpoint only after this
diagnostic commit passes and its report is inspected.

It must:

1. Validate the new diagnostic commit as the exact HEAD/origin baseline.
2. Validate the two pending source hashes and exact diff shape.
3. Validate Patch 518/519 success evidence by exact hashes.
4. Treat Patches 520–524 as consumed pre-write failures by exact hashes;
   do not search their logs for terminal-only failure text.
5. Use semantic source/runtime checks rather than escaped-string counts.
6. Stage exactly the two approved OAuth backend files.
7. Verify the staged allowlist and staged `diff --check`.
8. Commit and push only those two application files.
9. Preserve Claude and ChatGPT tokens, Hermes direct Bearer state,
   write-disabled settings, inventory, lifecycle data, deployment,
   instance secret, and restore staging.
10. Leave abandoned OAuth-row cleanup for a separate later patch.

## Conclusion

No application-source correction is required. The next operation is a
narrow two-file checkpoint based on this exact diagnostic baseline.
