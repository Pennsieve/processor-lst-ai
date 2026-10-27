"""Container entry point: runs main() once and exits with its status (no Lambda mode)."""
import sys

from processor.main import main

sys.exit(main())
