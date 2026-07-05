# Saving your work in egm-studio

**What this is:** how to save the things you notice — *observations* and
*figures* — in the egm-studio desktop app, and how they get organized into a
phase. **Who it's for:** anyone using egm-studio to explore banks and write up
findings.

## Where your work lives: a phase, or scratch

Saved work lands in one of two places:

- A **phase** — a curated, self-contained set of artifacts for one project
  phase. Open an existing one with **File ▸ Open phase**, or start a fresh one
  with **File ▸ New phase**.
- **Scratch** — your personal staging area, for when you haven't opened a phase
  yet or aren't ready to commit something to one. Scratch behaves just like a
  phase (same tree, the same status dots, the same right-click viewers), but it
  lives in your own app-data folder. You can point it somewhere else in
  **Settings ▸ Scratch folder**.

## Saving an observation

When you notice something worth remembering, choose **File ▸ Save observation**.
Write a short note (required), optionally link it to earlier observations, and
save. egm-studio also remembers your current **view** — which banks are loaded,
your filter, and your selection — so opening the observation later reloads
exactly what you were looking at.

- With a phase open, pick **Add to scratch** or **Add to phase**.
- With no phase open, the observation goes to scratch.

Right-click an observation in the tree to **Open** it (reload its view) or
**Edit** it (revise the note).

## Saving a figure

In the figure-prep view, use **Save into… ▸ Add to scratch | Add to phase** to
write the figure spec so it can be regenerated later. The figure remembers which
banks it draws from.

## Promoting scratch work into a phase

Right-click a scratch item and choose **Promote to phase** to move it into the
currently open phase. If that item depends on other things in scratch — for
example, a figure needs the banks it plots — those are **pulled in
automatically**, so you never end up with a figure in the phase whose banks are
missing. To promote only the item itself, turn off **Settings ▸ Automatically
add dependencies**.

## Reading the status dots

Each tree item carries a small status indicator:

- **Green** — present and valid.
- **Grey ring** — present, but not yet validated.
- **Red** — the file is missing.
- **Amber** — either the file is malformed, *or* something it references isn't
  available. Hover the item for a tooltip that says which.

Run **Validate phase** to check both well-formedness and dependency
completeness. A scratch item can satisfy its dependencies from scratch *or* the
open phase; a phase item must find everything within the phase itself.
