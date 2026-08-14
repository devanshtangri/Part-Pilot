# Diagnostic 690 — Live-sync diagnostic evidence contract recovery

Generated: `2026-08-14T14:01:23.441440+00:00`

## Current state

- Chat: `Chat 24: Authenticated Live Sync and Public Alpha Hardening`
- Patch range: `686-710`
- Starting `HEAD == origin/main`: `cf6fa2d3c6b33b2e12bdf25216b035dab77f8775`
- Runtime: `image=sha256:7a285a3ebb7eccf9eddb7c375a2b5616773e5aa40283ce270e41aff445ad23b9 health=healthy restart=0`
- Alembic: `0016_mcp_tool_permissions (head)`
- Working tree/index: clean.
- Production SQLite integrity passes.
- Authoritative session table is `sessions`; `user_sessions` does not exist.
- `backend/app/main.py` matches the Git `HEAD` blob at SHA-256 `79800e370b0268c8cf59c2e803098ee536687a1e0f91f20e6be32e21d2b168c6`.
- This patch is documentation-only.

## Patch 687

Patch 687 used the correct main.py SHA and reached the copied-database live-sync smoke. The smoke queried `user_sessions` instead of the authoritative `sessions` table.

- Script SHA-256: `ffac0c91aaad7143bbd6a55b5872920bcfb12affdfb96de9018590844219e6dd`
- Log SHA-256: `1d10f965609979e207070c72223dd2c987d07b12eedc2afaf1f510c1b9dce240`

## Patch 688

Patch 688 was generated with an unsafe broad patch-number replacement. It changed digits inside the baseline SHA literal.

```text
actual: 79800e370b0268c8cf59c2e803098ee536687a1e0f91f20e6be32e21d2b168c6
wrong:  79800e370b0268c8cf59c2e803098ee536688a1e0f91f20e6be32e21d2b168c6
```

The repository itself did not drift.

- Script SHA-256: `7dc2001d86755bc6085bab0f68cbf939df21f01a0a5f1d05501b30621d8f561a`
- Log SHA-256: `689c3701977a44be3fefb02055510d17a8b38f8bb6c40049604d7d5f50d065eb`

## Patch 689

Patch 689 correctly pinned the Patch 688 script/log hashes but incorrectly required terminal failure-summary text to exist inside Patch 688's durable log.

The durable logger records step notes plus commands/stdout/stderr from `State.run()`. The exception handler prints the final `Phase`, `Exception`, `Failing command`, rollback and Git summary to the terminal but does not append that summary to the log. Therefore Patch 689's assertion was invalid.

- Script SHA-256: `e22d3c3f31643a3ca4ee8afe30504a49e70ec37ec718271145163b2b22425a07`
- Log SHA-256: `c1629b4249ee6368394138eb4793c292070a174d8092b9647448b047caa92039`
- Pinned Patch 688 script SHA: `7dc2001d86755bc6085bab0f68cbf939df21f01a0a5f1d05501b30621d8f561a`
- Pinned Patch 688 log SHA: `689c3701977a44be3fefb02055510d17a8b38f8bb6c40049604d7d5f50d065eb`

## Durable diagnostic evidence contract

1. Pin consumed scripts and durable logs by SHA-256.
2. Validate failure facts from reproducible script/source state and command evidence actually persisted in logs.
3. Do not require terminal-only failure-summary strings in `fixes/logs/*` unless a patch explicitly writes them there.
4. Never globally replace patch numbers across hashes, candidate bytes, markers or evidence paths.
5. Scope transformations to explicit verified metadata/functions/blocks.

## Safe Patch 691 recovery plan

1. Start from the Patch 690 diagnostic checkpoint.
2. Validate exact application source and Patch 687/688/689 evidence.
3. Reconstruct the five-file backend live-sync candidate explicitly in memory.
4. Preserve broker, authenticated `/api/live/events`, protected `/api/live/state`, replay/resync, topic revisions and lifecycle-aware stream termination.
5. Correct the copied-database smoke to use `sessions`.
6. Compile all generated Python before writes.
7. Keep rehearsals isolated from live source/deployment.
8. Require exactly the intended five-file pending set and a clean index.
9. Run canonical Docker build plus copied-database live-sync, lifecycle and complete smokes.
10. Deploy only the exact image that passed all copied-database smokes.
11. Preserve production SQLite, credentials, MCP policy, instance secret and real data.
12. Leave backend live-sync source uncommitted/unpushed for frontend/browser integration.

## Conclusion

Repository source, runtime and production data remain healthy. Patch 690 establishes the diagnostic evidence contract needed to resume implementation safely.
