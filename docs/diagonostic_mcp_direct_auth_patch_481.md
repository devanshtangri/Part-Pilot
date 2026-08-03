# Patch 481 MCP Direct Authentication Diagnostic

Generated: `2026-08-03T12:29:07.353053+00:00`

## Result

The committed `/mcp` runtime currently accepts OAuth bearer tokens through
`Authorization: Bearer`. A direct static Bearer key would use the same header,
so it must have a unique Part Pilot prefix such as `pp_mcp_key_` and be enabled
only through an explicit direct-auth mode.

OAuth credentials are stored as one-way SHA-256 hashes. That supports
validation, but it cannot support the planned Reveal and Copy controls. The
repository currently has no instance-secret setting, Fernet/envelope helper or
cryptography dependency. Direct-key storage therefore needs its own encrypted
persistence contract before runtime or frontend work begins.

## Git and deployment

- HEAD/origin: `730df55ccff146ba57d6fe4d70a47ad4f0c8af64`
- Working tree and index: clean
- Deployment image: `sha256:9b226405be13bf00fac3806731f4f0d6396d390efe56f4a083d895dd65992f06`
- Health: `healthy`
- Restart count: `0`
- Started: `2026-08-03T06:53:03.011983964Z`

## Database

- SHA-256 at start: `bfdaf210a98ca9163c836b2c5ed5a428a1706cd2925004691c3adf6f70dcfd6b`
- Alembic: `0008_mcp_oauth`
- Integrity: `ok`
- Foreign-key violations: `0`
- Parts: `15`
- Projects: `7`
- Reservations: `9`
- Sessions: `3`
- Audit rows: `105`
- OAuth clients: `0`
- OAuth tokens: `0`
- MCP settings: `{"mcp.enabled": {"value_json": "false", "value_text": null}, "mcp.read_tools_enabled": {"value_json": "false", "value_text": null}, "mcp.write_tools_enabled": {"value_json": "false", "value_text": null}}`

## Security observations

- Instance-secret configuration exists: `False`
- `cryptography` dependency exists: `False`
- Fernet usage exists: `False`
- Persistent `/data` mount exists: `True`
- Client-address trust logic exists in MCP runtime: `False`

## Required credential contract

1. Direct mode is explicit and separate from OAuth.
2. Bearer keys use `pp_mcp_key_` plus at least 32 random bytes.
3. Validation uses a non-reversible digest and `hmac.compare_digest`.
4. Reveal/Copy requires encrypted-at-rest plaintext in addition to the digest.
5. Encryption derives from a stable instance secret, never an ephemeral
   container-only value.
6. Rotation atomically replaces ciphertext and digest and immediately
   invalidates the old key.
7. Audits never contain plaintext, ciphertext, complete digests or request
   authorization headers.
8. `last_used_at` updates are throttled rather than written on every request.
9. `mcp.enabled` and `mcp.read_tools_enabled` remain mandatory gates.
10. Write authorization stays ineffective until safeguarded write tools exist.

## Recommended persistence

Use a dedicated singleton table rather than generic `app_settings`:

- `id`
- `mode`
- `key_ciphertext`
- `key_digest`
- `key_prefix`
- `custom_header_name`
- `rotated_at`
- `last_used_at`
- `created_at`
- `updated_at`

The migration must not create or enable a key automatically. Existing behavior
remains OAuth-only until an authenticated administrator explicitly configures
direct authentication.

## Safe Patch 482 plan

1. Add Alembic revision `0009_mcp_direct_auth` and a dedicated model.
2. Add the stable instance-secret configuration contract.
3. Add encryption, generation, digest, create/rotate/reveal and validation
   primitives for Bearer-key mode only.
4. Add copied-database smoke tests for migration, encryption round-trip,
   wrong-key rejection, atomic rotation, redacted audits and no-op behavior.
5. Do not modify the MCP runtime, frontend, custom-header mode, trusted-network
   mode or tool registry in Patch 482.
6. Build and deploy the backend foundation, verify Alembic and the complete
   smoke suite, and preserve inventory, Projects, Reservations, sessions,
   audits, OAuth rows and restore staging.
7. Commit and push the backend-only slice after all checks pass.

## Exact inspected source hashes

- `backend/alembic/versions/0008_mcp_oauth.py`: `c2cee34a6a2c155b79e659a6c5ef88039788c32f6bd9969858789d849d71cb76`
- `backend/app/api/routes/app_settings.py`: `d94c443427e4f6e5cb318d18841ebdb19b4ef30a39c8696b781688920bda5420`
- `backend/app/core/config.py`: `9bbcdac5e5d8475268527d1296f3df3a756ac240f21f0ffeaef0ed49f9812715`
- `backend/app/mcp/runtime.py`: `07157a2a0dc7c3a7dc1d8a38854a02a72ebb01be5521e550288ae859889b600a`
- `backend/app/schemas/app_settings.py`: `6b35d67dd9a3d898614edb69a4a410db8c3e544b61dcdc860630354c76129fa5`
- `backend/app/services/app_settings.py`: `b560f496458c0ac84309f1571e75d762b4d3126654b56d41c2db381e593d1c07`
- `backend/app/services/mcp_oauth.py`: `c99b36f95ae1c0a1f413a9905f7d85377449b256397df2aaa636008510b1af51`
- `backend/requirements.txt`: `93d2de24c07c861ae4886624e9723c7cb5dbbff06802285c87d00edcb0541dec`
- `docker-compose.yml`: `934bad061fbfe00cb05eb1d1cebb800d311a9c3f7b87c5f90a495c44c627b903`
