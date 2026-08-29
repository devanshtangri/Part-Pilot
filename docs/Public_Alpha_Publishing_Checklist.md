# Part Pilot — Public Alpha Publishing Checklist

<!-- PARTPILOT:PUBLIC_ALPHA_PUBLISHING_CHECKLIST:V798 -->

This checklist separates already-verified release evidence from actions that still
require an explicit repository-owner decision. The verified source boundary is Patch 796;
the publishing-documentation recovery checkpoint is Patch 798.

## Already verified

- [x] Chat 27 release-candidate boundary completed and pushed.
- [x] Working release candidate has a clean synchronized `main` checkpoint.
- [x] Canonical Docker/Vite build reproduces the approved runtime image.
- [x] Production schema is `0022_mcp_inventory_part_lifecycle`.
- [x] 44 copied-production backend release smokes pass.
- [x] Browser release-polish batch P779-P785 is approved.
- [x] Real Claude OAuth MCP discovery plus safeguarded write preview/confirmation tested.
- [x] Repository release hygiene excludes tracked production DB, `.env`, instance-secret,
  private-key/PEM/certificate artifacts.
- [x] README contains deployment-security guidance.
- [x] Tag-neutral public-alpha release notes are prepared.

## Repository-owner decisions — completed before consequential publishing

- [x] Release tag/title selected: `v1.0.0` / `Part Pilot v1.0.0`.
- [x] Licensing selected and explicitly approved: `Part Pilot Source-Available License
  Version 1.0` for Part Pilot's original materials; third-party components retain their
  own licenses.
- [x] GitHub Release classification selected: stable/final release, **not** pre-release.

These owner decisions are now fixed release inputs; automated publication must not
substitute different values.

## Pre-publication repository checks

- [ ] Confirm `HEAD == origin/main` and the worktree/index are clean immediately before
  creating a tag/release.
- [ ] Confirm runtime health and SQLite/Alembic integrity if the live deployment remains
  part of release evidence.
- [ ] Confirm no credentials, `.env`, database, backup archive or instance secret are
  staged or included in release assets.
- [ ] Review `README.md` and `docs/Public_Alpha_Release_Notes.md` for the exact release
  title/tag chosen by the owner, if the release should mention them.
- [x] Add only the explicitly approved project license in its own reviewed patch and
  update README/release-note wording consistently.

## GitHub Release actions

- [ ] Create the chosen Git tag from the exact approved commit.
- [ ] Push the tag and verify it resolves to the intended commit.
- [ ] Create the GitHub Release using `docs/Public_Alpha_Release_Notes.md` as the source.
- [ ] Apply the owner's chosen pre-release/final-release setting.
- [ ] Do not attach production databases, backups, `.env`, instance secrets or credentials.
- [ ] Verify repository About/description and README do not make licensing claims that
  conflict with the owner's chosen disposition.

## Post-publication verification

- [ ] Open the public repository/release page and verify README/release-note links render.
- [ ] Verify the published tag points to the intended commit.
- [ ] Clone the public tag into a clean temporary directory and confirm Docker Compose
  setup instructions are internally consistent.
- [ ] Confirm no sensitive artifacts are present in the tag/release assets.
- [ ] Record the published tag/release URL and release commit in the next durable checkpoint.

## Alpha support boundaries

- Notifications & Messaging remain post-v1 unless explicitly reprioritized.
- Permanent inventory purge remains outside MCP.
- Fix only genuine release blockers discovered during publishing/distribution; avoid
  product redesign as part of release ceremony.
