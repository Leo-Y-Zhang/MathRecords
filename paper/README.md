# Paper source

`main.tex` is the LaTeX source of *Five new mixed van der Waerden numbers*,
and `main.pdf` is the compiled paper.
It is a single self-contained file: no `.bib`, no figures, standard packages
only (`geometry`, `amsmath`, `amssymb`, `amsthm`, `booktabs`, `microtype`,
`hyperref`).

## Building

Any mainstream TeX distribution works:

```sh
# tectonic (single binary, fetches packages on first run)
tectonic paper/main.tex

# or a full TeX Live / MiKTeX
pdflatex main.tex && pdflatex main.tex   # twice, for cross-references
```

`main.pdf` is committed so the paper can be read without a TeX installation.
The source remains the artifact: the PDF is rebuilt from `main.tex`, never
edited, and any change to the paper is a change to the source.

## Relationship to the repository

The paper is a write-up of what this repository already establishes and
claims nothing beyond it. `PAPER.md` at the repository root is the working
technical record the paper was drafted from; the certificates printed in the
paper are the same strings shipped in `vdw/` and checked by
`vdw/verify_certificate.py`, and every number in the paper's tables comes
from the `probe_*.json` / `crosscheck_*.json` result records.
