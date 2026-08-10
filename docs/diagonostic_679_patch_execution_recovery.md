# Diagnostic 679 — Patch execution recovery without terminal-log assumptions

Generated: `2026-08-10T21:59:49+00:00`

## Current state

- Repository: `/projects/Part Pilot`
- Branch: `main`
- Baseline HEAD/origin before this diagnostic: `0d38f96be206a87d4bc65a947486e2732d3ef975` (`Checkpoint Preferences targeted resets`)
- Runtime image: `sha256:2eece00c42bb9ae36d9231ced821dd89ec54f86b38ff3c3024df44ab4442f2fb`
- Runtime health/restart: `healthy / 0`
- Alembic: `0016_mcp_tool_permissions (head)`
- Index before diagnostic: clean
- Application/database/deployment writes by Patch 679: **none**
- Only this report may be staged, committed and pushed.

Exact pending Patch 675 browser-test status:

```text
 M backend/app/api/routes/app_settings.py
 M backend/app/schemas/app_settings.py
 M backend/app/services/app_settings.py
 M frontend/src/auth/AuthContext.tsx
 M frontend/src/components/AddPartModal.tsx
 M frontend/src/components/EditPartModal.tsx
 M frontend/src/pages/PartManager.tsx
 M frontend/src/pages/Settings.tsx
 M frontend/src/services/settingsClient.ts
 M frontend/src/types/settings.ts
?? backend/app/db/currency_settings_smoke_test.py
```

### Pending Patch 675 hashes

- `backend/app/api/routes/app_settings.py` — `925f9a34aa3baed5592e7e9428a6d58a9c59f6d8d571f15b172ba94237662579`
- `backend/app/schemas/app_settings.py` — `ea174112848575bcd9f3d0a71f29d3c448b91ae8c189401b9c8889ba75f5e9b9`
- `backend/app/services/app_settings.py` — `4b52c7240c49aa7e9e1b628dcff190631a09059399b00f9915b63ea0c23c70a8`
- `backend/app/db/currency_settings_smoke_test.py` — `a0e47349e8b86ce8d9e62a9cf54697a65028ec4f3661106ae1bcd9d03cbb4a23`
- `frontend/src/auth/AuthContext.tsx` — `19dfdda4f84dcaed3f31aa748de19c8aa7df9a918e18b79f6d37a15a0ca13d48`
- `frontend/src/components/AddPartModal.tsx` — `dd2251af891e6a2a0783221189b020f52312638902c5f08cab1437f8ca3fee0a`
- `frontend/src/components/EditPartModal.tsx` — `1daf2e0e73c25d1ce8bcd5f50d313eb6b49d291171e2559c561cc270bd1a5626`
- `frontend/src/pages/PartManager.tsx` — `92888f1b5bbf995f2fc22ecfc91d457ec583799503d5c7ef4af2387196c17815`
- `frontend/src/pages/Settings.tsx` — `bcd852361c8a5f5bf6968ed59a240c6eff3757d65ccf879d4289f86a11596a18`
- `frontend/src/services/settingsClient.ts` — `ae5c236006a83439c43f3dab45b62f672a461fadab6e5936241f0d7c21abefa2`
- `frontend/src/types/settings.ts` — `4644c561503e11159930ed8397ce01eed97ec96988772b172aa845ae74cfafba`

## Immutable evidence

- `fixes/675_add_iso_currency_preference.py` — `2de405ef244bd8dc8c5ad483eb72c181677b816a0f6c6f0eebc870ace477673e`
- `fixes/logs/675_iso_currency_preference_20260810-174216.log` — `a1ed379d81e058618b739046a4ea7a0942420315da01e2a2d4188353b754c24e`
- `fixes/676_theme_regional_display_and_timezone.py` — `3d69fc304fc03a2055c06d7657a5c91b408a5768fd0f3988d5dbd8e4a3498775`
- `fixes/logs/676_regional_display_timezone_20260810-210305.log` — `3a60d352f8eaeba5e9e22afcdb3da5aa550c70c642937fea3805208151b96d03`
- `fixes/677_document_explicit_patch_execution_rule.py` — `6a8cf7fe873de98155f8f0f545ce0f17149de3946b00f740b89b1a08194aa06d`
- `fixes/logs/677_explicit_patch_execution_rule_20260810-212835.log` — `a0130e0f69e047be6cc2ecce52a56a6dfd2f12c455d7f6b78d54d446c46fbb08`
- `fixes/678_diagnose_patch_execution_recovery.py` — `fe98b77713f62478a9fa4391c5bef436a959d9bc7de7ff581c3803694acd12c1`
- `fixes/logs/678_patch_execution_recovery_diagnostic_20260810-213538.log` — `b4d21fe0d8a9d6ab7cf8e88bd2c8c804d1fca758ef57ce6d94b6c82065b0e43c`

### Patch 675 durable-log shape

- `675_log_validation_banner`: `1`
- `675_log_service_marker`: `1`
- `675_log_ui_marker`: `1`
- `675_log_terminal_success_literal`: `0`
- `675_script_terminal_success_print`: `1`

This proves the important distinction: Patch 675's script has exactly one success-path `print("Everything PASS")`, while its durable log contains zero copies of that terminal-only final line. The durable log separately contains its successful validation/runtime evidence.

## Root cause — Patch 676

Patch 676's immutable source reads the Patch 675 durable log and includes `Everything PASS` in the required marker tuple. It then rejects any missing marker. Since the exact Patch 675 durable log contains zero copies of that terminal-only final line, Patch 676's preflight predicate is structurally unsatisfiable for the actual successful Patch 675 run.

Patch 679 deliberately does **not** require Patch 676's terminal exception text to exist inside its durable log. The Patch 676 durable log proves it entered the relevant preflight, while the root cause is proven directly from immutable Patch 675/676 bytes.

## Root cause — Patch 677

Patch 677's immutable source probes Docker with `.State.RestartCount`. Docker exposes the container restart counter at top-level `.RestartCount`.

Reproduced read-only bad-probe stderr:

```text
template parsing error: template: :1:44: executing "" at <.State.RestartCount>: map has no entry for key "RestartCount"
```

Correct read-only probe:

```text
sha256:2eece00c42bb9ae36d9231ced821dd89ec54f86b38ff3c3024df44ab4442f2fb healthy 0
```

Patch 679 therefore proves this root cause directly and does not depend on Patch 677's terminal stderr being copied into its durable log.

## Root cause — Patch 678

Patch 678 repeated the same evidence-model mistake: its immutable source required terminal exception strings from Patch 676 and Patch 677 to exist in their durable logs. Those logs are command/progress logs, not complete terminal transcripts. Exact durable-log counts for those terminal-only strings are:

- Patch 676 terminal exception literal: `0`
- Patch 677 Docker terminal exception literal: `0`
- Patch 678 terminal exception literal in its own durable log: `1`

The diagnostic rule going forward is: **prove failures from immutable source logic plus reproducible/read-only facts; never require terminal-only exception or final-success output to appear in durable logs unless the producing script explicitly persists it there.**

## Stale repository memory still pending recovery

`docs/Part_Pilot_Project_Memory.txt` remains byte-identical to its Patch 674 version (`502cffa0ca65c82c5f24f17ea8876f2f55a3e3cf7508dfb87a2f5070ad9d779a`). Because Patch 677 failed before writes, it still contains both stale rules:

- `User runs scripts; assistant never executes numbered patches.`
- `Keep this memory <=8000 bytes.`

These are intentionally **not** changed by this diagnostic.

## Safe recovery plan

1. **Patch 680 — documentation recovery only.** Update `docs/Part_Pilot_Project_Memory.txt` so numbered patches may be executed by the assistant only when the user explicitly requests that specific patch; on such a request execute exactly the requested command once and return the full raw output only, with no diagnosis/retry/fix/extra command in that execution turn. Replace the accidental 8K repository-memory cap with a context-conscious target of `<=20,000 characters`, while keeping ChatGPT Project Memory under its separate 8K limit. Use the correct top-level Docker `.RestartCount` probe. Preserve and leave unstaged every Patch 675 application byte.
2. **Patch 681 — Regional display/timezone browser-test recovery.** Reapply the already validated V676 candidate on top of the exact Patch 675 pending source, but remove terminal-only durable-log predicates. Validate source hashes, clean index, runtime/Alembic, copied-DB smokes, canonical Docker build and runtime markers. Leave the combined browser-test source uncommitted for browser approval.
3. **Patch 682 — checkpoint after explicit browser approval.** Commit/push the approved currency + timezone source and update durable docs. Do not checkpoint before browser approval.

## Guardrails for Patch 680+

- Do not infer successful/failed terminal output from durable logs unless the script explicitly writes that output into the log.
- Keep all browser-test application source uncommitted until explicit browser approval.
- Do not rewrite stored timestamps when workspace timezone changes.
- Currency remains formatting/display semantics only; no FX conversion or historical numeric rewrite.
- Do not mutate live SQLite while rehearsing patch generators; copied databases only.
- Preserve exact pending source/index bytes across documentation-only work.
