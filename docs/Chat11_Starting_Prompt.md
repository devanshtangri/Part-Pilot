# Ready-to-paste starting prompt

<!-- PARTPILOT:CHAT10_BOUNDARY:V250 -->
<!-- PARTPILOT:CHAT10_BOUNDARY_RECOVERY:V253 -->

Use the exact chat title:

`Chat 11: Stored Parts Search Finalization`

Paste this into the new chat only after Patch 253 reports `Everything PASS`:

---

Continue the Part Pilot project from:

`docs/Chat10_to_Chat11_Handoff.md`

Also inspect:

- `docs/Checkpoint.md`
- `docs/Implementation_Roadmap.md`
- `docs/Part_Pilot_Project_Memory.txt`
- `README.md`

This chat title is exactly:

Chat 11: Stored Parts Search Finalization

Start with Patch 254. Patch 275 is the
mandatory final Python file of this chat.

The local working tree intentionally contains only:

- frontend/src/pages/PartManager.tsx
- frontend/src/pages/PartManager.css

These are the pending Patch 248 browser-test changes. Do not discard them.

Patch 249 failed before backup or write because its validator rejected the
generic token `box-shadow:` even though the intended flat card CSS used
`box-shadow: none !important;`.

Patch 254 must apply the dashboard-search-like red treatment
to the complete Stored Parts out-of-stock card while scoping validation
correctly.

Keep the 70 Patch 241 temporary fixtures until browser approval. Their package
values were repaired to NULL by Patch 245. After approval, remove only
manifest-owned fixture records, verify real inventory is unchanged, then
commit and push the approved frontend batch.

Continue the sequential downloadable Python patch workflow. Successful scripts
must print exactly:

Everything PASS

Diagnostic Markdown filenames must begin with:

diagonostic_

Do not ask for manual source edits.

---
