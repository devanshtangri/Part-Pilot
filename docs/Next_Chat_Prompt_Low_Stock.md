# Part Pilot — Next Chat Starting Prompt

Continue development of **Part Pilot** from the latest `main` branch:

```text
https://github.com/devanshtangri/Part-Pilot
```

Before proposing any source change, read these files directly from GitHub:

1. `docs/Phase4_Location_Filtering_to_Low_Stock_Handoff.md`
2. `docs/Checkpoint.md`
3. `docs/Implementation_Roadmap.md`
4. `README.md`

The previous browser-tested Stored Parts location batch passed. My exact test
response was:

```text
everything pass
```

The completed checkpoint includes:

- reusable location catalogue management;
- location assignment during part creation and metadata editing;
- optional backend `location_id` filtering;
- correct filtered totals and pagination;
- Stored Parts **All locations** selector;
- location-aware search, counts, empty states, table rows, and Part Details;
- responsive desktop, tablet, and mobile styling;
- complete smoke, build, deployment, route, and browser verification.

Start the next slice with **read-only Diagnostic 174** for low-stock and
settings-driven out-of-stock behaviour. Inspect the existing low-stock fields,
calculation helpers, dashboard targets, app-settings infrastructure, locked
out-of-stock grouping decision, relevant API/client/UI boundaries, and smoke
patterns. Do not modify application source in the diagnostic.

Before assuming the local repository matches GitHub, have me run or inspect:

```bash
cd "/projects/Part Pilot"
git status --short --branch
git log -4 --oneline
```

Mandatory workflow:

- Give every implementation or fix as one complete downloadable Python file.
- Never ask me to manually find and edit source lines.
- Preflight all transformations completely in memory before source writes.
- Back up all changed files.
- Compile Python where applicable.
- Run `git diff --check`.
- Build and deploy Part Pilot for application changes.
- Run the complete smoke suite.
- Verify deployed frontend bundles and relevant routes.
- Roll back safely on failure.
- Print the exact line `Everything PASS` last and only on complete success.
- Leave browser-dependent changes uncommitted until I approve them.
- Use separate implementation and documentation commits.
- Preserve unrelated untracked files.
- Keep patches small and independently verifiable.

Do not combine the next slice with reservations, projects, backups, MCP, or a
full universal-search rewrite.
