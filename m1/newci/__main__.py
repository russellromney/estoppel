"""Entry point: `python path/to/newci <command>` or `python -m newci <command>`."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
sys.path.insert(0, str(HERE.parent))

from newci.cli import main  # noqa: E402

sys.exit(main())
