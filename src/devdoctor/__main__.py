"""Allow running DevDoctor directly via python -m devdoctor."""

import sys
from devdoctor.cli import main

if __name__ == "__main__":
    sys.exit(main())
