"""PROVENANCE.md quotes hashes of generated files. They must match the files, or a sceptic's first check fails."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "PROVENANCE.md").read_text(encoding="utf-8")


def _sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_the_quoted_hashes_of_the_certified_results_are_the_files_hashes() -> None:
    quoted = dict(re.findall(r"^([0-9a-f]{64})  (results/\w+\.json)$", DOC, flags=re.M)[i][::-1] for i in range(3))
    assert set(quoted) == {"results/payoffs.json", "results/bootstrap.json", "results/sensitivity.json"}
    for path, digest in quoted.items():
        assert _sha(path) == digest, f"{path}: PROVENANCE.md quotes a hash that no longer matches. Regenerate and update it."


def test_the_abbreviated_bundle_and_exhibition_hashes_match_too() -> None:
    for path in ("courtroom/viz/web/data/bundle.js", "courtroom/viz/web/data/exhibition.js"):
        digest = _sha(path)
        pattern = rf"`{digest[:8]}\.\.\.{digest[-4:]}`"
        assert re.search(pattern, DOC), f"PROVENANCE.md does not quote the current hash of {path}: {digest[:8]}...{digest[-4:]}"


def test_every_command_the_page_tells_you_to_run_exists() -> None:
    subcommands = set(re.findall(r"python -m courtroom ([a-z][a-z-]*)", DOC))
    source = (ROOT / "courtroom" / "cli.py").read_text(encoding="utf-8")
    assert {"verify", "analysis", "export", "export-exhibition", "stress"} <= subcommands
    for name in subcommands:
        assert f'add_parser("{name}"' in source, f"PROVENANCE.md runs `courtroom {name}`, which is not a command"
