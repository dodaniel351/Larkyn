"""Dev launcher: `python run.py` (equivalent to `python -m larkyn`)."""

import sys

from larkyn.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
