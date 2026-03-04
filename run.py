"""Legacy entrypoint for backwards compatibility.

All core functionality now lives in the `core` package.
"""

from core import *  # re-export public API
from core.cli import main


if __name__ == "__main__":
    main()