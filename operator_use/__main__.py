import sys
from operator_use.cli.commands import app

if __name__ == "__main__":
    # Ensure sys.argv[0] is handled gracefully by typer
    app()
