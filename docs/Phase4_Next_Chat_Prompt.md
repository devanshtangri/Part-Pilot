# Part Pilot — Next Chat Starting Prompt

Paste the following into a new Part Pilot project chat:

---

Open and follow the current Part Pilot handoff directly from GitHub:

https://raw.githubusercontent.com/devanshtangri/Part-Pilot/main/docs/Phase4_Inventory_Details_Package_Catalogue_Handoff.md

Treat that GitHub handoff and the current repository as the source of truth.
Inspect the repository before changing anything because local or remote state
may have advanced.

Continue with the exact next step specified in the handoff: create Diagnostic
132 for the stock-movement and quantity-adjustment workflow.

Mandatory rules:

- Give every diagnostic, fix, or implementation as a complete Python file.
- Never ask me to find lines or manually copy-paste source changes.
- Keep each patch small and narrowly scoped.
- Back up changed files and roll back on failure.
- Run compilation, `git diff --check`, Docker build/deploy, Alembic checks,
  the complete smoke suite, bundle checks, and route checks where applicable.
- Print the exact final line `Everything PASS` only after every intended
  operation and verification succeeds.
- Do not commit implementation work until I confirm the browser test.
- Maintain `docs/Checkpoint.md`, `docs/Implementation_Roadmap.md`, and the
  active handoff at meaningful checkpoint commits.

Start by fetching the GitHub handoff and then generate the complete read-only
`132_inspect_stock_movement_targets.py` file.
