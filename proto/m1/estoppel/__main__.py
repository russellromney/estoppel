"""Entry point: `python path/to/estoppel <command>` or `python -m estoppel <command>`."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]
sys.path.insert(0, str(HERE.parent))

from estoppel.cli import main  # noqa: E402

sys.exit(main())
