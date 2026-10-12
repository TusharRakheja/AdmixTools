#!/usr/bin/env python3
"""Generate a deterministic synthetic EIGENSTRAT dataset for regression tests.

The dataset has real admixture structure, so qpAdm should recover weights
close to the simulated ones.  That gives the golden outputs independent
credibility: they are not merely "whatever the binary printed", they can be
checked against a known answer.

Population tree (drift simulated with the Balding-Nichols model):

    root
    |-- A ---- S1              Target = 0.50*S1 + 0.30*S2 + 0.20*S3
    |     \\-- RA -- R1, R2
    |-- B ---- S2
    |     \\-- RB -- R3, R4
    \\-- C ---- S3
          \\-- R5

Each right population is differentially related to exactly one source, which
is what gives the f4 matrix enough rank for qpAdm to estimate weights.

Everything is driven by a single seed, so output is byte-identical on every
platform: only Python's standard library is used, and no floating point value
ever reaches the output files (genotypes are small integers).

Usage:  gen_testdata.py <outdir> [--seed N]
Writes: synth.geno synth.snp synth.ind left1 right1 poplist
        par.qpAdm par.qpfstats par.convertf
"""

import argparse
import os
import random
import sys

# ---------------------------------------------------------------- parameters

NUM_CHROM = 10            # chromosomes
SNPS_PER_CHROM = 2000     # -> 20000 SNPs total
CHROM_LENGTH_M = 1.0      # Morgans per chromosome
IND_PER_POP = 20
MISSING_RATE = 0.02       # fraction of genotypes set to 9 (no data)

# These defaults were chosen empirically: at 20000 SNPs / 20 individuals per
# population, qpAdm recovers the simulated weights below to within about 0.02
# across seeds, while qpAdm and qpfstats each run in under 3 seconds.  Smaller
# datasets are noise-dominated and make the known-truth check meaningless.

TRUE_WEIGHTS = [("S1", 0.50), ("S2", 0.30), ("S3", 0.20)]

# (name, parent, Fst-from-parent).  Order matters only for reproducibility.
TREE = [
    ("A",  "root", 0.02),
    ("B",  "root", 0.02),
    ("C",  "root", 0.02),
    ("S1", "A",    0.03),
    ("RA", "A",    0.05),
    ("R1", "RA",   0.04),
    ("R2", "RA",   0.04),
    ("S2", "B",    0.03),
    ("RB", "B",    0.05),
    ("R3", "RB",   0.04),
    ("R4", "RB",   0.04),
    ("S3", "C",    0.03),
    ("R5", "C",    0.05),
]

SOURCES = ["S1", "S2", "S3"]
RIGHTS = ["R1", "R2", "R3", "R4", "R5"]
TARGET = "Target"
# Sampled populations, in the order individuals appear in the .ind/.geno files.
SAMPLED = [TARGET] + SOURCES + RIGHTS


def drift(rng, p, fst):
    """Balding-Nichols: draw a child frequency given parent frequency p."""
    if fst <= 0.0:
        return p
    # Guard the Beta parameters away from zero; betavariate rejects alpha<=0.
    c = (1.0 - fst) / fst
    a = max(p * c, 1e-6)
    b = max((1.0 - p) * c, 1e-6)
    return rng.betavariate(a, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--snps-per-chrom", type=int, default=SNPS_PER_CHROM)
    ap.add_argument("--ind-per-pop", type=int, default=IND_PER_POP)
    args = ap.parse_args()

    snps_per_chrom = args.snps_per_chrom
    ind_per_pop = args.ind_per_pop
    rng = random.Random(args.seed)
    os.makedirs(args.outdir, exist_ok=True)
    out = lambda n: os.path.join(args.outdir, n)

    # ------------------------------------------------------------- .ind file
    individuals = []   # (id, sex, population)
    for pop in SAMPLED:
        for i in range(1, ind_per_pop + 1):
            individuals.append(("%s_%d" % (pop, i), "U", pop))

    with open(out("synth.ind"), "w", newline="\n") as f:
        for iid, sex, pop in individuals:
            f.write("%20s %s %12s\n" % (iid, sex, pop))

    # ----------------------------------------------------- .snp and .geno
    geno_lines = []
    snp_lines = []
    spacing = CHROM_LENGTH_M / snps_per_chrom

    for chrom in range(1, NUM_CHROM + 1):
        for j in range(snps_per_chrom):
            genpos = (j + 1) * spacing
            physpos = (j + 1) * 20000
            snp_lines.append(
                "%-20s %3d %12.6f %12d %s %s"
                % ("snp_%d_%d" % (chrom, j + 1), chrom, genpos, physpos, "A", "G")
            )

            # Ancestral frequency, then drift down the tree.
            freq = {"root": rng.uniform(0.10, 0.90)}
            for name, parent, fst in TREE:
                freq[name] = drift(rng, freq[parent], fst)
            # Admixed target is a linear mixture of the source frequencies.
            freq[TARGET] = sum(w * freq[s] for s, w in TRUE_WEIGHTS)

            row = []
            for _iid, _sex, pop in individuals:
                if rng.random() < MISSING_RATE:
                    row.append("9")
                    continue
                p = freq[pop]
                g = (1 if rng.random() < p else 0) + (1 if rng.random() < p else 0)
                row.append(str(g))
            geno_lines.append("".join(row))

    with open(out("synth.snp"), "w", newline="\n") as f:
        f.write("\n".join(snp_lines) + "\n")
    with open(out("synth.geno"), "w", newline="\n") as f:
        f.write("\n".join(geno_lines) + "\n")

    # ------------------------------------------------------------ pop lists
    # qpAdm popleft: target first, then the candidate sources.
    with open(out("left1"), "w", newline="\n") as f:
        f.write("\n".join([TARGET] + SOURCES) + "\n")
    with open(out("right1"), "w", newline="\n") as f:
        f.write("\n".join(RIGHTS) + "\n")
    # qpfstats poplist: first population is the base and must be a true diploid.
    with open(out("poplist"), "w", newline="\n") as f:
        f.write("\n".join(RIGHTS + SOURCES + [TARGET]) + "\n")

    # ----------------------------------------------------------- par files
    # seed: is pinned explicitly -- qpAdm otherwise seeds from getpid()+time()
    # and prints different numbers on every run.
    with open(out("par.qpAdm"), "w", newline="\n") as f:
        f.write(
            "indivname:    synth.ind\n"
            "snpname:      synth.snp\n"
            "genotypename: synth.geno\n"
            "popleft:      left1\n"
            "popright:     right1\n"
            "details:      YES\n"
            "allsnps:      YES\n"
            "inbreed:      NO\n"
            "seed:         314159\n"
        )

    with open(out("par.qpfstats"), "w", newline="\n") as f:
        f.write(
            "indivname:     synth.ind\n"
            "snpname:       synth.snp\n"
            "genotypename:  synth.geno\n"
            "poplistname:   poplist\n"
            "fstatsoutname: fstats.txt\n"
            "allsnps:       YES\n"
            "inbreed:       NO\n"
            "scale:         NO\n"
            "seed:          314159\n"
        )

    with open(out("par.convertf"), "w", newline="\n") as f:
        f.write(
            "genotypename:    synth.geno\n"
            "snpname:         synth.snp\n"
            "indivname:       synth.ind\n"
            "outputformat:    PACKEDANCESTRYMAP\n"
            "genotypeoutname: packed.geno\n"
            "snpoutname:      packed.snp\n"
            "indivoutname:    packed.ind\n"
        )

    sys.stderr.write(
        "wrote %d SNPs x %d individuals (%d populations) to %s, seed=%d\n"
        % (len(geno_lines), len(individuals), len(SAMPLED), args.outdir, args.seed)
    )
    sys.stderr.write(
        "true admixture weights: %s\n"
        % ", ".join("%s=%.2f" % (s, w) for s, w in TRUE_WEIGHTS)
    )


if __name__ == "__main__":
    main()
