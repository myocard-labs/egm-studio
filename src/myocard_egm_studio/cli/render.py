"""``egm-studio-render`` — the headless figure-render console script.

Reads a figure_spec ``.json``, validates it through egm-data's typed loader
(per ADR-001 — egm-studio never parses the JSON itself), renders it via
:func:`myocard_egm_studio.figures.render`, and writes the image. Importable as
``main`` for tests; wired as the ``egm-studio-render`` console script.

Real-data rendering before Block 7: a spec's ``inputs.groups`` carry bank *ids*,
not paths. Block 7 resolves those ids through the phase manifest; until then
pass the id->path map by hand with ``--banks MAP.json`` (a ``{bank_id: path}``
JSON, i.e. a proto-manifest) and/or repeated ``--bank BANK_ID=PATH``. With a
map supplied the CLI loads the banks and renders real data; with none it exits 4
asking for one.

If the output file already exists the CLI skips it (exit 0) *before* loading any
data, so re-running a phase's specs only renders what's missing; pass
``--overwrite`` to re-render.

Usage
-----
::

    egm-studio-render SPEC.json [-o OUTPUT] [--banks MAP.json] [--bank ID=PATH ...] [--overwrite]

Exit codes: 0 success (or output already exists and was skipped); 1 file/render
error; 2 invalid spec (malformed JSON or schema mismatch); 3 unknown recipe; 4
no figure data available (no map passed, or the recipe has no loader wired yet);
5 figure-data loading failed (bad path, unreadable bank, or an unmapped bank id).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from myocard_egm_data.phases import load_figure_spec
from pydantic import ValidationError

from myocard_egm_studio.figures import (
    FigureDataNotLoadedError,
    LoaderNotRegisteredError,
    UnknownRecipeError,
    render,
    resolve_recipe_data,
)


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
    p.add_argument(
        "--banks",
        type=Path,
        default=None,
        metavar="MAP.json",
        help=(
            "JSON file mapping bank_id -> path (a proto-manifest for the Block 7 "
            "manifest resolution). Merged with --bank; --bank wins on key conflicts."
        ),
    )
    p.add_argument(
        "--bank",
        action="append",
        default=None,
        metavar="BANK_ID=PATH",
        help=(
            "Map one spec bank_id to a bank file on disk (repeatable). Example: "
            "--bank lpred_synth_val_2026-06-25=/data/preds_synth.h5"
        ),
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-render even if the output file already exists (default: skip it).",
    )
    return p


def _collect_bank_paths(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> dict[str, str]:
    """Build the ``{bank_id: path}`` map from ``--banks`` (JSON) + ``--bank`` flags.

    ``--bank`` entries override ``--banks`` keys. Malformed input is reported via
    ``parser.error`` (exit 2), the argparse convention.
    """
    paths: dict[str, str] = {}
    if args.banks is not None:
        try:
            raw = json.loads(Path(args.banks).read_text(encoding="utf-8"))
        except OSError as exc:
            parser.error(f"cannot read --banks file {args.banks}: {exc}")
        except json.JSONDecodeError as exc:
            parser.error(f"--banks file {args.banks} is not valid JSON: {exc}")
        if not isinstance(raw, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
        ):
            parser.error(
                f"--banks file {args.banks} must be a JSON object of bank_id -> path strings."
            )
        paths.update(raw)
    for item in args.bank or []:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            parser.error(f"--bank expects BANK_ID=PATH, got {item!r}.")
        paths[key] = value
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

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

    # Skip an already-rendered figure before doing any (potentially slow) data
    # loading. Re-rendering is opt-in via --overwrite.
    out_path = args.output if args.output is not None else Path(spec.output.path)
    if out_path.exists() and not args.overwrite:
        print(f"{out_path} already exists; skipping (pass --overwrite to replace).")
        return 0

    bank_paths = _collect_bank_paths(args, parser)

    data = None
    if bank_paths:
        try:
            data = resolve_recipe_data(spec, bank_paths)
        except LoaderNotRegisteredError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 4
        except (OSError, ValueError) as exc:
            # FileNotFoundError on a bad path, or a loader/adapter rejection
            # (UnmappedBankIdError + the adapter's ValueErrors are ValueError).
            print(f"ERROR loading figure data: {exc}", file=sys.stderr)
            return 5

    try:
        out_path = render(spec, data=data, output_path=args.output, overwrite=args.overwrite)
    except UnknownRecipeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except FigureDataNotLoadedError:
        print(
            "ERROR: no figure data provided. Pass --banks MAP.json or repeated "
            "--bank BANK_ID=PATH to render from real predictions banks. "
            "(Spec-driven loading via the phase manifest lands in Block 7.)",
            file=sys.stderr,
        )
        return 4
    except (OSError, ValueError) as exc:
        print(f"ERROR rendering figure: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
