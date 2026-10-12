#!/bin/sh
# Assemble a self-contained Windows bundle from an already-built Cygwin tree.
#
# Must run inside Cygwin.  Produces a directory that works on a machine with
# no Cygwin installed, once <bundle>/bin is on PATH.
#
# Usage: make_bundle.sh <srcdir> <bundledir>
#
#   srcdir     the AdmixTools src/ directory, already built (make all; make install)
#   bundledir  created/overwritten; receives the bundle
#
# Layout matters.  cygwin1.dll derives the POSIX root from its OWN directory:
# the directory holding it becomes /bin and the parent becomes /.  Putting the
# executables in <bundle>/bin therefore makes /var/tmp land INSIDE the bundle,
# which is what qpAdm's fstats path and gzipped input need.  A flat layout puts
# /var/tmp outside the bundle and those paths fail.

set -eu

if [ $# -ne 2 ]; then
    echo "usage: $0 <srcdir> <bundledir>" >&2
    exit 2
fi

SRCDIR=$(cd "$1" && pwd)
BUNDLE="$2"

case "$(uname -s)" in
    CYGWIN*) ;;
    *) echo "make_bundle: must run under Cygwin, not $(uname -s)" >&2; exit 1 ;;
esac

rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/bin" "$BUNDLE/var/tmp" "$BUNDLE/tmp" "$BUNDLE/LICENSES"
: > "$BUNDLE/var/tmp/.keep"
: > "$BUNDLE/tmp/.keep"

# ---------------------------------------------------------- 1. executables
# Prefer the installed tree, which also carries the helper scripts.
if [ -d "$SRCDIR/../bin" ] && ls "$SRCDIR/../bin"/*.exe >/dev/null 2>&1; then
    cp -r "$SRCDIR/../bin"/* "$BUNDLE/bin/"
else
    cp "$SRCDIR"/*.exe "$BUNDLE/bin/"
fi

# -------------------------------------- 2. transitive Cygwin DLL closure
# Computed, not hard-coded: Cygwin keeps cyglapack-0.dll in /usr/lib/lapack
# rather than /usr/bin, and cygcheck silently omits DLLs it cannot locate, so
# objdump plus an explicit search path is the reliable combination.
SEARCH="/usr/bin /bin /usr/lib/lapack"

find_dll() {
    for d in $SEARCH; do
        if [ -f "$d/$1" ]; then echo "$d/$1"; return 0; fi
    done
    return 1
}

# Seeds: the bundled executables, plus the userland tools system() needs.
SEEDS=$(ls "$BUNDLE/bin"/*.exe)
for t in sh grep cp gzip; do
    p=$(find_dll "$t.exe") || { echo "make_bundle: $t.exe not found" >&2; exit 1; }
    cp "$p" "$BUNDLE/bin/"
    SEEDS="$SEEDS $p"
done
# fgrep and gunzip are #!/bin/sh wrappers, so they need sh.exe above.
for s in fgrep gunzip; do
    p=$(find_dll "$s") || true
    [ -n "${p:-}" ] && cp "$p" "$BUNDLE/bin/"
done

WANT=""
QUEUE="$SEEDS"
while [ -n "$QUEUE" ]; do
    NEXT=""
    for f in $QUEUE; do
        for d in $(objdump -p "$f" 2>/dev/null | awk '/DLL Name/ {print $3}'); do
            case "$d" in cyg*|lib*) ;; *) continue ;; esac
            case " $WANT " in *" $d "*) continue ;; esac
            WANT="$WANT $d"
            p=$(find_dll "$d") || { echo "make_bundle: cannot locate $d" >&2; exit 1; }
            NEXT="$NEXT $p"
        done
    done
    QUEUE="$NEXT"
done

for d in $WANT; do
    cp "$(find_dll "$d")" "$BUNDLE/bin/"
done

# ------------------------------------------------- 3. docs and licences
# dist/ holds the end-user documentation shipped inside the zip, so a bundle
# built from a fresh checkout is complete without anything added by hand.
DIST="$SRCDIR/../dist"
cp "$DIST/README-WINDOWS.txt" "$BUNDLE/README-WINDOWS.txt"
cp "$DIST/NOTICE.txt"         "$BUNDLE/LICENSES/NOTICE.txt"

cp "$SRCDIR/LICENSE.txt" "$BUNDLE/LICENSES/AdmixTools-BSD-3-Clause.txt"
for f in /usr/share/doc/Cygwin/CYGWIN_LICENSE; do
    [ -f "$f" ] && cp "$f" "$BUNDLE/LICENSES/Cygwin-LICENSE.txt"
done
for f in /usr/share/doc/Cygwin/COPYING; do
    [ -f "$f" ] && cp "$f" "$BUNDLE/LICENSES/GPL-3.0.txt"
done

NDLL=$(ls "$BUNDLE/bin"/*.dll | wc -l)
NEXE=$(ls "$BUNDLE/bin"/*.exe | wc -l)
echo "make_bundle: $NEXE executables, $NDLL DLLs in $BUNDLE/bin"
echo "make_bundle: DLL closure:$WANT"
