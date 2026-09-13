"""PyInstaller entry point.

meeting_agent/__main__.py uses a relative import (`from .main import main`),
which only works when Python loads it as a package submodule -- PyInstaller's
onefile bootloader runs the entry script as a bare top-level script instead,
so that import breaks with "attempted relative import with no known parent
package" (reproduced by actually running the built binary). This script uses
the equivalent absolute import instead, which works either way.
"""
from meeting_agent.main import main

if __name__ == "__main__":
    main()
