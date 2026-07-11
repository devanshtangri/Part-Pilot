# Part Pilot Design System

## Direction

Part Pilot should look like practical, polished application software rather than a marketing page.

Primary visual inspiration:

- Seerr-style dark application shell
- Compact navigation
- Thin borders and restrained shadows
- Dense, readable inventory tables
- Clear status colors and one primary accent
- Functional hierarchy before decorative styling

## Core principles

1. **Application-first**
   - Prioritize navigation, search, filters, tables, and data density.
   - Avoid landing-page hero sections inside the authenticated app.

2. **Restrained surfaces**
   - Use deep navy/charcoal surfaces.
   - Use thin visible borders instead of glassmorphism.
   - Avoid excessive gradients, glowing cards, oversized rounded corners, and floating pill clusters.

3. **Compact typography**
   - Page titles should be clear but not oversized.
   - Labels, table headers, metadata, and navigation should remain compact.
   - Use generous spacing only where it improves scanning.

4. **Inventory-oriented layouts**
   - Desktop inventory views should favor full-width tables.
   - Keep columns sortable and filterable.
   - Use compact row heights with clear hover and selection states.
   - Status, stock level, and availability should be understandable at a glance.

5. **Color**
   - Dark navy is the base.
   - Emerald remains the Part Pilot primary accent.
   - Reserve warning, danger, and success colors for real status information.
   - Do not use accent color decoratively everywhere.

6. **Consistency**
   - Standard panel radius: 8–12 px.
   - Standard input/button height: approximately 42–44 px.
   - Standard borders: one-pixel muted blue-gray.
   - Shadows should be subtle and used only for major floating surfaces.

## Authentication screen

- Use one unified setup/login window.
- Both columns must share the same height.
- Left side provides concise installation context.
- Right side contains the form.
- No personal example values may be hardcoded.
- No marketing badges, glass cards, or oversized hero typography.

## Future authenticated interface

- Seerr-like fixed sidebar on desktop.
- Prominent global search near the top.
- Inventory pages should be table-first.
- Secondary navigation may use tabs under the page title.
- Actions should be grouped near the relevant data, not scattered across cards.
