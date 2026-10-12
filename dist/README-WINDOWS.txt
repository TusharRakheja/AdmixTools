ADMIXTOOLS 8.1.0 -- Windows build  (build v8.1.0-win-1)
=================================================

Native Windows executables. Cygwin does NOT need to be installed; every
required runtime library is included.

Upstream source : https://github.com/DReichLab/AdmixTools
Windows build   : https://github.com/TusharRakheja/AdmixTools
                  branch v8.1.0-win-1, tag v8.1.0-1


INSTALLING
----------
1. Unzip anywhere, e.g. C:\Tools\admixtools-8.1.0-win-1
2. Add the "bin" subfolder to your PATH, e.g.
       C:\Tools\admixtools-8.1.0-win-1\bin
3. Open a NEW terminal and check:
       qpDstat
   You should see the usage message.

Works from cmd.exe, PowerShell and Windows Terminal.


IMPORTANT -- KEEP THE FOLDER STRUCTURE
--------------------------------------
Do not move individual .exe files out of "bin", and do not delete the
"var" or "tmp" folders. The layout is load-bearing:

  admixtools-8.1.0-win-1\
      bin\       executables + DLLs + a minimal POSIX shell
      var\tmp\   scratch space for gzipped input
      tmp\       scratch space
      LICENSES\

Several programs (qpGraph, qpAdm, qpWave, qpfstats, convertf) run helper
commands internally via a shell. The bundled cygwin1.dll locates that
shell relative to its own directory, which is why "bin" must stay "bin"
and must keep sh.exe, grep.exe, cp.exe and gzip.exe beside the DLLs.
Copying just an .exe somewhere else will fail at runtime.


USING IT
--------
Use FORWARD SLASHES for paths in parameter files:

    genotypename:  C:/data/mydata.geno        <-- do this

Backslashes work for most programs, but they silently break anything that
goes through the internal shell -- in particular gzipped input, where the
path is handed to gunzip and the shell consumes the backslashes:

    genotypename:  C:\data\my.geno.gz
      -> gzip: C:datamy.geno.gz: No such file or directory

Forward slashes are accepted by every program here, so use them
throughout and the problem never arises. Relative paths are fine too.

Run the tools exactly as documented upstream:

    qpDstat -p parfile > out.log
    convertf -p par.convert
    transpose in.geno out.geno
    transpose --low-mem in.geno out.geno


GZIPPED INPUT
-------------
A genotypename ending in .gz is decompressed automatically into
/var/tmp (i.e. the bundle's var\tmp folder). This path runs through the
internal shell, so the genotypename MUST use forward slashes -- see
USING IT above. Those scratch files are NOT
cleaned up afterwards, so delete var\tmp\genotmp* occasionally. To use a
different scratch location, set it in the parameter file:

    trashdir:  C:/temp


KNOWN LIMITATIONS
-----------------
* Helper scripts are included but need interpreters that are NOT bundled:
    - bin\*.pl, bin\jackdiff, bin\mkpretty, bin\numlines, bin\getresult,
      bin\xtractcol*          require Perl
    - bin\rexpfit.r            requires R
    - bin\script\*.py          requires Python 3
  The compiled .exe programs need none of these.

* The example parameter files in the upstream repository expect a data
  directory that is not distributed here. Download the dataset
  "Affymetrix Human Origins (2012)" from the Reich Lab website and place
  it as ..\data relative to the examples.

* If you already have Cygwin installed, do not put both this bin folder
  and C:\cygwin64\bin on PATH at the same time. Two different cygwin1.dll
  versions in one process tree conflict. Either use this bundle on its
  own, or build from source inside your Cygwin installation.

* These binaries are 64-bit (x86-64). There is no 32-bit build.


BUILT FROM
----------
Upstream ADMIXTOOLS 8.1.0, with Windows build fixes. Compiled with Cygwin
GCC 13, linking GSL 2.3, OpenBLAS 0.3.25 and LAPACK 3.12.0.

See LICENSES\NOTICE.txt for the full list of bundled components, their
licences, and where to obtain their source. The aggregate is governed by
GPL-3.0-or-later because AdmixTools links GSL.
