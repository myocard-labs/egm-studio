# Reference applications

Block 0.4 of the egm-studio design phase. Dissect a small set of
production tools whose UX feel we want to learn from, then translate
the findings into concrete egm-studio decisions (layout, theme,
interaction patterns).

**Three reference targets** were chosen after a short candidate review:

1. **RStudio (Posit)** — scientific IDE with a predictable pane layout.
   Closest aesthetic match for "tool a researcher sits in for hours."
2. **JupyterLab** — interactive-computing workspace. Source of the
   interactive-widget pattern Daniel called out as directly useful for
   v1_baseline parameter exploration.
3. **Intracardiac mapping systems (CARTO 3 / EnSite X / Rhythmia HDx)**
   — composite reference for multi-trace EGM display. The three major
   vendors have independently converged on essentially the same EGM
   panel layout, which makes this the most authoritative reference for
   that specific concern.

**DaVinci Resolve** was considered but dropped — the clinical mapping
systems cover the multi-trace density question more directly without
being out-of-domain.

## 1. RStudio

### Layout — fixed 4-pane grid

Per the Posit user guide, RStudio has four primary panes plus an
optional sidebar:

- **Source** (default top-left) — code editor; multi-tab; can be
  popped out to its own window for multi-monitor work; can be split
  into additional "source columns" (only to the left of the primary
  panes — arbitrary placement is not supported).
- **Console** (default bottom-left) — REPL + integrated Terminal tab +
  Background Jobs tab.
- **Environment** (default top-right) — Environment / History /
  Connections / Build / VCS / Tutorial tabs cycle in this region.
- **Output** (default bottom-right) — Files / Plots / Packages / Help
  / Viewer / Presentation tabs cycle in this region.
- **Sidebar** (left or right; hidden by default) — configurable to
  host any tab from Environment or Output.

**Layout rules:**

- All four primaries are always visible — only min/max within column,
  never fully hidden.
- Gray separator lines are draggable for resizing.
- `Tools > Global Options > Pane Layout` to remap which tabs go in
  which pane.
- Tabs can tear out into independent windows (multi-monitor support).

**Why the strict grid works:** predictable mental model — you learn
the four quadrants once and the layout never surprises you. Within
each quadrant, related-but-not-simultaneously-used views (Files /
Plots / Help / Viewer) tab-cycle because you only look at one at a
time anyway.

**Why it doesn't fit egm-studio exactly:** intracardiac traces are
*long* signals. Cramming them into a quadrant wastes their primary
informative dimension (time). RStudio's grid optimizes for the
"medium-size views, evenly distributed" case; we need a layout that
lets traces occupy the full window width when the user wants to see
them.

### Theme

Dark/light toggle is first-class — Posit's own docs have a "Toggle
dark mode" button. Editor theme separately configurable for Console
and Source panes. Density isn't an explicit setting but the default
typography (small monospace, generous-but-not-excessive line spacing)
sets the bar for "scientific IDE that doesn't feel cramped."

### What we borrow / what we don't

| Borrowed | Skipped |
|---|---|
| Tab cycling within a region for related-but-not-simultaneous views | Strict 4-quadrant grid (too rigid for trace display) |
| Min/max within column + draggable separators | "Source columns only on the left" rule (RStudio-specific) |
| Tear-out into separate window (multi-monitor for paper-figure-prep) | Tools > Options > Pane Layout (overkill for one user) |
| Optional collapsible sidebar | |
| Dark/light toggle first-class | |

## 2. JupyterLab

### Layout — free-form dock workspace

Per the project docs:

- **Menu bar** (top) — File / Edit / View / Run / Kernel / Tabs /
  Settings / Help.
- **Left sidebar** — file browser, running kernels & terminals,
  command palette, table of contents, extension manager. Uses an
  "Activity Bar" (icon column) to switch between tabs.
- **Right sidebar** — property inspector (notebook-aware), debugger.
- **Main work area** — dock panel where tabs can be dragged to
  subdivide / split / arrange freely.
- **Down area** — additional widget region added in newer versions
  (PR #10201).

**Layout rules:**

- Drag a tab to the edge of any panel to subdivide.
- Tabs move freely between left sidebar / right sidebar / main / down
  area.
- **Workspaces** — saved named layouts (file open + panel arrangement)
  accessible via URL or commands. *Direct real-world precedent for our
  Save schema (ADR-017).*
- **Simple Interface mode** — toggle to temporarily focus on a single
  activity, then restore the multi-pane layout. Useful UX for
  paper-figure-prep where distraction kills focus.
- Sidebars collapse/expand independently.

**Why the free-form dock works for JupyterLab:** the tool is a
notebook + general-purpose workspace; users assemble their own
arrangements for very different jobs (data exploration, teaching,
literate computing).

**Why we don't want it for egm-studio:** the flexibility is overkill,
hard to test, and hard to write architectural ADRs around. We don't
need users dragging tabs into arbitrary arrangements; we need a
predictable, professional-feeling workspace they can master quickly.

### Theme

Light / Dark / System Settings toggle in the doc nav — also
first-class, same as RStudio.

### The ipywidgets `@interact` pattern (the standout)

The single most influential pattern from JupyterLab for our purposes:

```python
from ipywidgets import interact
import matplotlib.pyplot as plt

@interact(amplitude=(0.0, 2.0, 0.1), frequency=(1.0, 50.0, 1.0))
def plot_sine(amplitude, frequency):
    t = np.linspace(0, 1, 1000)
    plt.plot(t, amplitude * np.sin(2*np.pi*frequency*t))
```

The decorator parses tuple parameters as `(min, max, step)` →
auto-generates sliders → re-runs the function on slider drag → the
plot re-renders in real time. There's also `interact_manual` for
expensive functions, which adds a manual "Run" button instead of
re-running on every change.

**Why this matters for egm-studio:** Daniel specifically called out
this kind of pattern as directly useful for analyzing input data with
configurable parameters (drag threshold slider → see filtered trace;
drag dV/dt-max smoothing window slider → see activation-peak marker
shift on the trace). The pattern transfers to PyQtGraph + Qt sliders
with essentially zero architectural mismatch — just a different
framework expressing the same idea.

### What we borrow / what we don't

| Borrowed | Skipped |
|---|---|
| `@interact`-style slider → live re-render pattern (drives ADR-019) | Free-form dock (use a more constrained layout) |
| Saved workspaces concept (validates ADR-017 unified Save schema) | In-browser execution model (we're a desktop Qt app) |
| Simple Interface / focus mode toggle | Notebook cells / run buttons (we're not a notebook) |
| Activity Bar (icon column) for sidebar navigation | |
| Left + right sidebars, both collapsible | |
| First-class dark/light toggle | |

## 3. Intracardiac mapping systems (composite)

The three major vendors — Biosense Webster CARTO 3, Abbott EnSite X,
Boston Scientific Rhythmia HDx — have independently converged on
essentially the same EGM-panel layout. That convergence is strong
evidence that the pattern is the right one for any tool whose primary
job is helping a human compare multiple intracardiac signals.

### EGM panel pattern (common across all three)

- **Vertically-stacked traces** with a shared X-axis (time).
- **Left-column row labels** identifying each channel (e.g. `M1-M2`
  distal mapping pair, `CS20 D-2` for coronary sinus electrode 20
  distal-to-second). Labels are typically left-aligned in a fixed-width
  column.
- **Reference trace** — one trace designated as the timing anchor
  (typically the activation reference for local-activation-time
  measurement).
- **Per-channel filter controls** — HPF / LPF / 50–60 Hz notch toggles,
  configurable per channel. Rhythmia HDx exposes this in a
  catheter-control sidebar; CARTO and EnSite have similar arrangements.
- **Channel selection panel** separate from the trace display. Click a
  catheter → its channels appear in the EGM panel.
- **EGM panel occupies a horizontal slab of the screen** alongside the
  3D anatomy view; it never gets cramped into a quadrant.

### Vendor-specific notes

- **CARTO 3** — annotation window order: surface ECG leads I/II/III/V1
  → reference electrogram → distal mapping catheter electrogram
  (M1-M2). Dashboard includes contact-force gauge, force-vector
  display, real-time impedance graph. Visualizes up to 5 catheters
  simultaneously.
- **EnSite X** — newer system with explicit "new GUI" redesign vs the
  prior EnSite Precision platform. Activation sequence display uses
  REF + REF2 + active mapping channel stack. Markets a 10 µV RMS noise
  floor.
- **Rhythmia HDx** — densest of the three: 64-electrode Orion basket
  arranged as an 8×8 grid (A1-H8 labeling). 0.01 mV noise floor,
  1,000+ points/minute sampling.

### What we borrow / what we don't / what's out of scope for v0.1

| Borrowed for v0.1 | Future / not v0.1 | Out of scope (different repo entirely) |
|---|---|---|
| Vertically-stacked traces with shared X-axis | Per-channel HPF/LPF/notch toggles (ADR-019 territory) | 3D anatomy rendering |
| Left-column row labels (channel / `bank_id + trace_idx`) | "Reference trace" concept for activation-peak anchoring visualization | Real-time catheter tracking |
| Channel selection sidebar separate from trace display | | Force / impedance gauges |
| EGM panel occupies full-width slab, not a quadrant | | Live signal streaming |
| Time-scale slider / pan & zoom on X-axis (free with PyQtGraph) | | |

## Synthesis: the egm-studio layout

### Layout model — resizable columns with collapsible side panels

Constraints from the reference-app dissection + Daniel's explicit
input:

- **Not** RStudio's fixed 4-quadrant grid (traces need full window
  width).
- **Not** JupyterLab's free-form dock (too flexible, hard to test).
- Trace display must be able to span the full window width.
- One full-width main region or two side-by-side regions are both
  acceptable layouts.
- Optional collapsible left + right sidebars (channel-selection / filter
  controls on the left; Phase artifact tree on the right per the
  cross-artifact design).

This is captured as **ADR-025** below.

### Theme — dark default, light toggle

Both RStudio and JupyterLab treat dark/light as first-class. Clinical
mapping systems lean dark (cath-lab lighting), but our context is
researcher-in-an-office, where the dark/light choice is more personal
than functional. Daniel prefers dark; we default to dark and ship a
light toggle.

Captured as **ADR-012** below (promoted Deferred → Accepted).

### Interactive parameter exploration — `@interact`-equivalent

The JupyterLab ipywidgets pattern is the model. In PyQtGraph + Qt:
parameter sliders bound to plot-redraw callbacks, with debouncing for
expensive operations and an optional "Run" button for very expensive
ones (the `interact_manual` analog).

Captured as **ADR-019** below (promoted Deferred → Tentative; the
v1_baseline parameter-exploration use case is the concrete anchor).

### Multi-trace EGM viewer — composable widget, stacked, shared X-axis

Direct adoption of the clinical mapping system pattern. The trace
display is a **composable widget unit** (one `TraceWidget` instance
per trace, stacked vertically in a `GraphicsLayoutWidget` with shared
X-axis), not a singleton "the trace tab". v0.1 default `N=1`; later
phases scale to N=8, 20, 64 traces without rewriting plumbing.

Captured as **ADR-024** below (new).

## Implications summary for the open ADRs

| ADR | Before this study | After this study |
|---|---|---|
| 012 Theme | Deferred | **Accepted** — dark default + light toggle |
| 016 Framework lean | Open (PySide6 + pyqtgraph + matplotlib) | Unchanged; PyQtGraph + Qt sliders is the natural egm-studio equivalent of ipywidgets + matplotlib, no architectural mismatch |
| 017 Save schema | Accepted (cross-artifact deep-dive) | Reinforced — JupyterLab workspaces are an industry precedent |
| 019 Live-preview | Deferred | **Tentative** — `@interact` pattern transfers, concrete v0.1 use cases identified |
| 024 Composable trace widget | (didn't exist) | **New, Accepted** — captures clinical-system convergence + PyQtGraph alignment |
| 025 Layout model | (didn't exist) | **New, Accepted** — resizable columns + collapsible sidebars |

ADRs 013 (testing), 014 (figure spec), 015 (one-vs-many GUI), and the
others not listed above are unaffected by this study.

## References

### RStudio

- [Pane Layout — RStudio User Guide (Posit)](https://docs.posit.co/ide/user/ide/guide/ui/ui-panes.html)
- [Customizing the RStudio IDE (Posit support)](https://support.posit.co/hc/en-us/articles/200549016-Customizing-the-RStudio-IDE)

### JupyterLab

- [The JupyterLab Interface (project docs)](https://jupyterlab.readthedocs.io/en/stable/user/interface.html)
- [JupyterLab Application Shell and Layout (DeepWiki)](https://deepwiki.com/jupyterlab/jupyterlab/3.1-application-shell-and-layout)
- [Using Interact — ipywidgets docs](https://ipywidgets.readthedocs.io/en/latest/examples/Using%20Interact.html)
- [Ipywidgets with matplotlib (Kapernikov tutorial)](https://kapernikov.com/ipywidgets-with-matplotlib/)

### Intracardiac mapping systems

- [CARTO 3 System — J&J MedTech](https://www.jnjmedtech.com/en-US/product/carto-3-system)
- [CARTO 3 Fact Sheet (Biosense Webster)](https://www.biosensewebster.com/documents/carto3-fact-sheet.pdf)
- [Advanced Mapping and Navigation Modalities (Clinical Gate)](https://clinicalgate.com/advanced-mapping-and-navigation-modalities/)
- [CARTO mapping annotation window diagram (ResearchGate)](https://www.researchgate.net/figure/Annotation-window-for-the-CARTO-mapping-system-Represented-from-top-to-bottom-are-ECG_fig2_5580719)
- [EnSite X EP System (Abbott)](https://www.cardiovascular.abbott/us/en/hcp/products/electrophysiology/mapping-systems/ensite-x.html)
- [EnSite X customer presentation (PDF)](https://www.wwm.de/hubfs/abbott/content/abbott-customer-presentation-ensite.pdf)
- [Evolution of Abbott Mapping Technology (ESI → EnSite X)](https://jafib-ep.com/wp-content/uploads/2023/10/Evolution-of-Abbott-Mapping-Technology-from-ESI-to-the-EnSite%E2%84%A2-X-EP-System.pdf)
- [Rhythmia HDx brochure (Boston Scientific)](https://faktymedyczne.pl/resources/data/forms/stoiska_zwykle/105/rhythmia_hdx_brochure_final.pdf)
- [Rhythmia HDx Instructions for Use (Boston Scientific)](https://www.bostonscientific.com/content/dam/elabeling/ep/rhythmia-mapping-system/rhythmia_6-0_mappingsystem/51660904-01A_RHY_HDX_IFU_OUS_ML_s.pdf)
- [Rhythmia HDx user manual (ManualsLib)](https://www.manualslib.com/manual/2985890/Boston-Scientific-Rhythmia-Hdx.html)
- [INTELLAMAP ORION mapping catheter (64-electrode basket)](https://www.bostonscientific.com/en-US/products/catheters--mapping/orion/orion-indications.html)
