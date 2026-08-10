"""
cy_encrypt.cli
~~~~~~~~~~~~~~

Command-line interface entry point.

Uses only Python's built-in :mod:`argparse` module to avoid external
dependencies; the CLI relies solely on the standard library.
"""

import argparse
import logging

from cy_encrypt.tools import Translation
from cy_encrypt.version import __version__

# Configure logging with default format
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        The configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="cy_encrypt",
        description="cy_encrypt - Compile and encrypt Python source code.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version and exit.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path to the configuration file. (default: %(default)s)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # ``execute`` subcommand: run the full compile-and-encrypt workflow.
    execute_parser = subparsers.add_parser(
        "execute",
        help="Run the compile-and-encrypt workflow.",
        description="Run the full compile-and-encrypt workflow.",
    )
    execute_parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path to the configuration file. (default: %(default)s)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the command-line interface.

    Args:
        argv: Optional list of command-line arguments. Defaults to
            :data:`sys.argv` when omitted.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "execute":
        Translation(args.config).run()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
