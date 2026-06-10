"""Dev launcher: `python run.py` (equivalent to `python -m hermes`)."""

import sys

from hermes.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
