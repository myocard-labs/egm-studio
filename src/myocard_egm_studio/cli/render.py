"""``egm-studio-render`` — the headless figure-render console script.

Reads a figure_spec ``.json``, validates it through egm-data's typed loader
(per ADR-001 — egm-studio never parses the JSON itself), renders it via
:func:`myocard_egm_studio.figures.render`, and writes the image. Importable as
``main`` for tests; wired as the ``egm-studio-render`` console script.

At Block 2 the recipe registry is empty, so a valid spec exits non-zero with a
clear "unknown figure recipe" message — the plumbing is in place for Block 3 to
register the recipes.

Usage
-----
::

    egm-studio-render SPEC.json [-o OUTPUT]

Exit codes: 0 success; 1 file/render error; 2 invalid spec (malformed JSON or
schema mismatch); 3 unknown recipe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from myocard_egm_data.phases import load_figure_spec
from pydantic import ValidationError

from myocard_egm_studio.figures import UnknownRecipeError, render


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="egm-studio-render",
        description="Render a publication figure from a figure_spec JSON file.",
    )
    p.add_argument("spec", type=Path, help="Path to a figure_spec .json file.")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Override the spec's output.path (where the rendered image is written).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        spec = load_figure_spec(args.spec)
    except OSError as exc:
        print(f"ERROR: cannot read spec file {args.spec}: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"ERROR: invalid figure spec {args.spec}:\n{exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        # Malformed JSON (json.JSONDecodeError) or a non-object top level.
        print(f"ERROR: malformed figure spec {args.spec}: {exc}", file=sys.stderr)
        return 2

    try:
        out_path = render(spec, output_path=args.output)
    except UnknownRecipeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError) as exc:
        print(f"ERROR rendering figure: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
