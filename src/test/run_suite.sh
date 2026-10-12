#!/bin/sh
# Run the regression suite and leave all outputs in one directory.
#
# The same script runs on the Linux reference build and on the Windows/Cygwin
# build under test, so any difference in the outputs is a difference in the
# binaries, not in how they were invoked.
#
# Usage: run_suite.sh <bindir> <outdir>
#
#   bindir  directory holding the executables (names may or may not end .exe)
#   outdir  created if absent; receives generated data and all outputs
#
# Exits non-zero if any tool fails.

set -eu

if [ $# -ne 2 ]; then
    echo "usage: $0 <bindir> <outdir>" >&2
    exit 2
fi

BINDIR=$(cd "$1" && pwd)
OUTDIR="$2"
HERE=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$OUTDIR"
OUTDIR=$(cd "$OUTDIR" && pwd)

# qpAdm, qpWave and qpGraph run "qpfstats -p ..." through system(), resolving
# it from PATH by bare name.  Put the build under test first so each build
# calls its own helper: otherwise a stray qpfstats elsewhere on PATH wins, and
# if it was built for another platform the run dies with "Exec format error".
PATH="$BINDIR:$PATH"
export PATH

# Resolve a tool name to a path.  Check the .exe form FIRST: a tree that has
# been built for both platforms can hold a Cygwin foo.exe next to a Linux
# ELF foo, and on Cygwin the extensionless one gives "Exec format error".
tool() {
    if   [ -f "$BINDIR/$1.exe" ]; then echo "$BINDIR/$1.exe"
    elif [ -x "$BINDIR/$1" ];     then echo "$BINDIR/$1"
    else echo "run_suite: $1 not found in $BINDIR" >&2; exit 1
    fi
}

# Generate the dataset only if it is not already there.  Reusing an existing
# dataset lets the reference run and the run under test share byte-identical
# input, and lets this script work on Cygwin, which has no python3.
if [ -f "$OUTDIR/synth.geno" ]; then
    echo "== reusing existing dataset in $OUTDIR"
else
    echo "== generating synthetic dataset"
    python3 "$HERE/gen_testdata.py" "$OUTDIR"
fi

cd "$OUTDIR"

echo "== convertf: eigenstrat text -> packedancestrymap"
"$(tool convertf)" -p par.convertf > convertf.out 2>&1

echo "== transpose: packed -> transpose-packed"
"$(tool transpose)" packed.geno tgeno.geno > transpose.out 2>&1

echo "== transpose --low-mem (must agree with the default path)"
"$(tool transpose)" --low-mem packed.geno tgeno_lowmem.geno > transpose_lowmem.out 2>&1

echo "== merge_transpose: two inputs via an LF list file"
cp tgeno.geno tgeno2.geno
printf 'tgeno.geno\ntgeno2.geno\n' > list_lf.txt
"$(tool merge_transpose)" -l list_lf.txt -o merged.geno -i 482 -s f888b349 \
    > merge_transpose.out 2>&1

echo "== transpose: merged -> packed (round trip)"
"$(tool transpose)" merged.geno back.geno > transpose_back.out 2>&1

echo "== qpfstats"
"$(tool qpfstats)" -p par.qpfstats > qpfstats.out 2>&1

echo "== qpAdm"
"$(tool qpAdm)" -p par.qpAdm > qpAdm.out 2>&1

# ---------------------------------------------------------------------------
# Windows-port checks.  These are NOT golden-compared against the Linux
# reference, because pristine upstream fails them: upstream's merge_transpose
# strips only '\n' from list entries, so a CRLF list leaves a stray '\r' on
# the filename and it aborts.  The result is recorded for the caller to assert
# on, rather than failing the suite, so the same script still runs clean
# against the reference build.
# ---------------------------------------------------------------------------
echo "== extra: merge_transpose with a CRLF list file (Windows-port check)"
printf 'tgeno.geno\r\ntgeno2.geno\r\n' > list_crlf.txt
if "$(tool merge_transpose)" -l list_crlf.txt -o merged_crlf.geno \
        -i 482 -s f888b349 > merge_crlf.out 2>&1; then
    if cmp -s merged.geno merged_crlf.geno; then
        echo "CRLF_LIST=ok" > crlf_result.txt
    else
        echo "CRLF_LIST=mismatch" > crlf_result.txt
    fi
else
    echo "CRLF_LIST=failed" > crlf_result.txt
fi
echo "   $(cat crlf_result.txt)"

echo "== done; outputs in $OUTDIR"
