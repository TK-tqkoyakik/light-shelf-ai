from __future__ import annotations

import sys

from app.app import main, run_startup_self_check


if __name__ == "__main__":
    if "--check" in sys.argv:
        run_startup_self_check()
    else:
        main()
