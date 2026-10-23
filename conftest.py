"""pytest configuration for root-level test discovery."""

import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
