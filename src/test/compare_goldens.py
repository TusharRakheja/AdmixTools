#!/usr/bin/env python3
"""Compare a regression-suite run against the recorded Linux goldens.

The goldens are produced by the upstream Linux build, which is what the tools
are meant to print.  The build under test (normally Windows/Cygwin) is then
compared against them.  A mismatch means the port changed behaviour.

Two kinds of comparison:

  * Binary artifacts are compared by SHA-256.  Packed genotype files are
    produced by integer operations with deterministic headers, so they are
    expected to be byte-identical on every platform.  Any difference here is
    a real bug, not floating-point noise.

  * Numeric text outputs are compared field by field.  Non-numeric tokens must
    match exactly; numbers must agree within a relative tolerance, because
    different BLAS/LAPACK builds legitimately differ in the low-order digits.

Volatile lines (timings, memory use, PID-bearing temp paths) are filtered out
before comparison.

Usage:
    compare_goldens.py record  <rundir> <goldendir>
    compare_goldens.py compare <rundir> <goldendir> [--tolerance 1e-6]

Exit status is 0 when everything matches, 1 otherwise.
"""

import argparse
import hashlib
import os
import re
import sys

# The generated input dataset.  Verified before anything else: if a different
# Python version makes the generator emit different data, every downstream
# comparison would fail for the wrong reason, so this is reported separately
# and explicitly.
INPUT_ARTIFACTS = [
    "synth.geno",
    "synth.snp",
    "synth.ind",
]

# Outputs compared byte-for-byte, via checksum.
BINARY_ARTIFACTS = [
    "packed.geno",
    "packed.snp",
    "packed.ind",
    "tgeno.geno",
    "tgeno_lowmem.geno",
    "merged.geno",
    "back.geno",
]

# Outputs compared numerically, token by token.
NUMERIC_OUTPUTS = [
    "qpAdm.out",
    "qpfstats.out",
    "fstats.txt",   # qpfstats' actual product, named by fstatsoutname:
]

# Lines matching any of these are dropped before comparing: they carry
# timings, memory figures, process ids or absolute paths.
VOLATILE = [
    re.compile(r"^##end of "),
    re.compile(r"\bseconds cpu\b"),
    re.compile(r"\bMbytes in use\b"),
    re.compile(r"^removing "),
    re.compile(r"/tmp/"),
    re.compile(r"fsx\.[0-9]+"),
    re.compile(r"^tmp: "),
    re.compile(r"\bwall clock\b"),
    # qpfstats prints "time in dofstats: 0.340" -- a duration, not a result.
    re.compile(r"^time in "),
]

NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")

# The tools echo argv[0] and the commands they shell out to, so the output
# carries whatever absolute path they were invoked by.  Reduce those to a bare
# basename rather than dropping the lines: that keeps them under comparison
# while making them independent of where the build happens to live.
TOOL_NAMES = (
    "qpAdm|qpfstats|qpGraph|qpWave|qpfmv|qpmix|qpDstat|qp3Pop|qpF4ratio"
    "|convertf|transpose|merge_transpose|mergeit|multimerge"
)
TOOL_PATH = re.compile(r"\S*[/\\](%s)(\.exe)?\b" % TOOL_NAMES)


def normalize(line):
    return TOOL_PATH.sub(r"\1", line)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_volatile(line):
    return any(p.search(line) for p in VOLATILE)


def load_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return [normalize(ln.rstrip("\r\n")) for ln in f if not is_volatile(ln)]


def record(rundir, goldendir):
    os.makedirs(goldendir, exist_ok=True)
    manifest = []
    for name in INPUT_ARTIFACTS + BINARY_ARTIFACTS:
        src = os.path.join(rundir, name)
        if not os.path.exists(src):
            print("record: missing %s" % name, file=sys.stderr)
            return 1
        manifest.append("%s  %s" % (sha256(src), name))
    with open(os.path.join(goldendir, "checksums.txt"), "w", newline="\n") as f:
        f.write("\n".join(manifest) + "\n")

    for name in NUMERIC_OUTPUTS:
        src = os.path.join(rundir, name)
        if not os.path.exists(src):
            print("record: missing %s" % name, file=sys.stderr)
            return 1
        with open(os.path.join(goldendir, name), "w", newline="\n") as f:
            f.write("\n".join(load_text(src)) + "\n")

    print("recorded %d checksums and %d numeric outputs into %s"
          % (len(BINARY_ARTIFACTS), len(NUMERIC_OUTPUTS), goldendir))
    return 0


def compare_numeric(name, got, want, tol, failures):
    if len(got) != len(want):
        failures.append("%s: line count %d, expected %d"
                        % (name, len(got), len(want)))
        return
    worst = 0.0
    worst_at = None
    for i, (g, w) in enumerate(zip(got, want), start=1):
        gt, wt = g.split(), w.split()
        if len(gt) != len(wt):
            failures.append("%s:%d: %d fields, expected %d\n  got:  %s\n  want: %s"
                            % (name, i, len(gt), len(wt), g, w))
            continue
        for a, b in zip(gt, wt):
            if a == b:
                continue
            if NUMBER.match(a) and NUMBER.match(b):
                fa, fb = float(a), float(b)
                scale = max(abs(fa), abs(fb), 1e-30)
                rel = abs(fa - fb) / scale
                if rel > worst:
                    worst, worst_at = rel, (i, a, b)
                if rel > tol:
                    failures.append(
                        "%s:%d: %s vs expected %s (relative %.3g > %.3g)"
                        % (name, i, a, b, rel, tol))
            else:
                failures.append("%s:%d: token %r, expected %r" % (name, i, a, b))
    if worst_at:
        print("  %s: largest numeric difference %.3g at line %d (%s vs %s)"
              % (name, worst, worst_at[0], worst_at[1], worst_at[2]))
    else:
        print("  %s: identical" % name)


def compare(rundir, goldendir, tol):
    failures = []

    want = {}
    cpath = os.path.join(goldendir, "checksums.txt")
    with open(cpath) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                digest, name = ln.split(None, 1)
                want[name] = digest

    print("input dataset (generator reproducibility):")
    input_bad = False
    for name in INPUT_ARTIFACTS:
        path = os.path.join(rundir, name)
        if not os.path.exists(path):
            failures.append("%s: missing from run" % name)
            continue
        got = sha256(path)
        if got == want.get(name):
            print("  %s: match" % name)
        else:
            input_bad = True
            failures.append(
                "%s: input data differs from what the goldens were built from "
                "(sha256 %s, expected %s). The generator is seeded and uses only "
                "the standard library, so this usually means a different Python "
                "version. Regenerate the goldens rather than chasing the numeric "
                "diffs below." % (name, got, want.get(name)))
    if input_bad:
        print("\nFAILED: input dataset does not match the goldens' input.")
        for f in failures:
            print("  - %s" % f)
        return 1

    print("binary artifacts (expected byte-identical):")
    for name in BINARY_ARTIFACTS:
        digest = want.get(name)
        path = os.path.join(rundir, name)
        if not os.path.exists(path):
            failures.append("%s: missing from run" % name)
            continue
        got = sha256(path)
        if got == digest:
            print("  %s: match" % name)
        else:
            failures.append("%s: sha256 %s, expected %s" % (name, got, digest))

    print("numeric outputs (relative tolerance %.3g):" % tol)
    for name in NUMERIC_OUTPUTS:
        path = os.path.join(rundir, name)
        gold = os.path.join(goldendir, name)
        if not os.path.exists(path):
            failures.append("%s: missing from run" % name)
            continue
        compare_numeric(name, load_text(path), load_text(gold), tol, failures)

    if failures:
        print("\nFAILED (%d problem%s):"
              % (len(failures), "" if len(failures) == 1 else "s"))
        for f in failures[:40]:
            print("  - %s" % f)
        if len(failures) > 40:
            print("  ... and %d more" % (len(failures) - 40))
        return 1

    print("\nall comparisons passed")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "compare"])
    ap.add_argument("rundir")
    ap.add_argument("goldendir")
    ap.add_argument("--tolerance", type=float, default=1e-6)
    a = ap.parse_args()
    if a.mode == "record":
        return record(a.rundir, a.goldendir)
    return compare(a.rundir, a.goldendir, a.tolerance)


if __name__ == "__main__":
    sys.exit(main())
