"""
cy_encrypt.tools
~~~~~~~~~~~~~~~~

Compile Python source code into Cython dynamic libraries (``.so`` / ``.pyd``).

Workflow:
    1. Copy ``source_dir`` to ``source_dir_YYYY_MM_DD_HH_MM_SS``
       (directories listed in ``skip_cp_dirs`` are not copied).
    2. Walk through ``target_dir`` and select files that need to be compiled
       (``.py`` / ``.pyx`` / ``.pyw``).
    3. Compile the selected files, then remove intermediate artifacts
       (``.c`` / ``build`` / ``__pycache__`` / original source files).
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from Cython.Build import cythonize
from setuptools import setup

# Logger
logger = logging.getLogger(__name__)

# Cython compilation directives
COMPILER_DIRECTIVES: dict[str, Any] = {
    "language_level": 3,
    "always_allow_keywords": True,
}

# Suffixes of source files that can be compiled.
# ``.pyx`` is a Cython source file, ``.pyw`` is a Python window script.
COMPILE_SUFFIXES: tuple[str, ...] = (".py", ".pyx", ".pyw")


class Config:
    """Compilation configuration."""

    def __init__(
            self,
            source_dir: Path,
            target_dir: Path,
            skip_cp_dirs: list[str],
            skip_dirs: list[str],
    ) -> None:
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.skip_cp_dirs = skip_cp_dirs or []
        self.skip_dirs = skip_dirs or []


class Translation:
    """Compile and encrypt Python source code into Cython extensions.

    The class encapsulates the full compilation workflow: load the
    configuration, copy the source directory, scan the files to compile,
    compile them, and clean up the intermediate artifacts.
    """

    def __init__(self, config_path: str) -> None:
        self.config_path = Path(config_path)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def load_config(self) -> Config:
        """Parse a JSON configuration file and return a :class:`Config` object.

        Returns:
            A :class:`Config` object.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If a required configuration item is missing or invalid.
        """
        if not self.config_path.is_file():
            raise FileNotFoundError(
                f"Configuration file does not exist: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            params = json.load(f)

        source_dir_str = params.get("source_dir")
        if not source_dir_str:
            raise ValueError("Configuration item 'source_dir' is missing")

        source_dir = Path(source_dir_str).resolve()
        if not source_dir.is_dir():
            raise ValueError(f"'source_dir' is not a valid directory: {source_dir}")

        # Target directory: source directory name + timestamp, located in the
        # parent directory of the source directory.
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        target_dir = source_dir.parent / f"{source_dir.name}_{timestamp}"

        return Config(
            source_dir=source_dir,
            target_dir=target_dir,
            skip_cp_dirs=params.get("skip_cp_dirs", []),
            skip_dirs=params.get("skip_dirs", []),
        )

    # ------------------------------------------------------------------
    # Path matching utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _match_skip(rel_path: PurePosixPath, skip_list: list[str]) -> bool:
        """Check whether a relative path matches any entry in ``skip_list``.

        A path matches if it equals an entry in ``skip_list`` or if any of
        its parent directories is listed.

        Args:
            rel_path: Relative path (POSIX style).
            skip_list: List of paths to skip.

        Returns:
            ``True`` if the path should be skipped, ``False`` otherwise.
        """
        for pattern in skip_list:
            base = PurePosixPath(pattern)
            if rel_path == base or base in rel_path.parents:
                return True
        return False

    @staticmethod
    def _need_compile(rel_path: PurePosixPath, skip_dirs: list[str]) -> bool:
        """Determine whether a file needs to be compiled.

        Rules:
            - The file suffix must be in ``COMPILE_SUFFIXES``
              (``.py`` / ``.pyx`` / ``.pyw``).
            - ``__init__.py`` files are excluded.
            - Paths listed in ``skip_dirs`` are excluded.

        Args:
            rel_path: File path relative to ``target_dir``.
            skip_dirs: List of directories to skip.

        Returns:
            ``True`` if the file needs to be compiled, ``False`` otherwise.
        """
        if rel_path.suffix not in COMPILE_SUFFIXES:
            return False
        if rel_path.name == "__init__.py":
            return False
        return not Translation._match_skip(rel_path, skip_dirs)

    # ------------------------------------------------------------------
    # Step 2.1 - Copy
    # ------------------------------------------------------------------
    def copy_source_dir(self, config: Config) -> None:
        """Copy ``source_dir`` to ``target_dir``, skipping ``skip_cp_dirs``.

        Args:
            config: The compilation configuration.
        """
        # Remove the target directory if it already exists.
        if config.target_dir.exists():
            shutil.rmtree(config.target_dir)

        # Ensure the parent directories exist.
        config.target_dir.mkdir(parents=True)

        for root, dirs, files in os.walk(config.source_dir):
            # Compute the relative path.
            rel_root = PurePosixPath(os.path.relpath(root, config.source_dir))

            # Filter out subdirectories to skip (modifying ``dirs`` in place
            # affects the ``os.walk`` traversal).
            dirs[:] = [
                d
                for d in dirs
                if not self._match_skip(rel_root / d, config.skip_cp_dirs)
            ]

            # Copy files.
            for name in files:
                file_rel = rel_root / name
                if self._match_skip(file_rel, config.skip_cp_dirs):
                    continue

                src = Path(root) / name
                dst = config.target_dir / file_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # ------------------------------------------------------------------
    # Step 2.2 - Scan files to compile
    # ------------------------------------------------------------------
    def find_compile_files(self, config: Config) -> list[str]:
        """Scan ``target_dir`` for source files that need to be compiled.

        Args:
            config: The compilation configuration.

        Returns:
            List of file paths relative to ``target_dir`` (POSIX style,
            e.g. ``"utils/helper.py"``).
        """
        result: list[str] = []

        for root, dirs, files in os.walk(config.target_dir):
            rel_root = PurePosixPath(os.path.relpath(root, config.target_dir))

            # Filter out subdirectories to skip.
            dirs[:] = [
                d
                for d in dirs
                if not self._match_skip(rel_root / d, config.skip_dirs)
            ]

            # Collect files that need to be compiled.
            for name in files:
                file_rel = rel_root / name
                if self._need_compile(file_rel, config.skip_dirs):
                    result.append(str(file_rel))

        return result

    # ------------------------------------------------------------------
    # Step 2.3 - Compile + cleanup
    # ------------------------------------------------------------------
    @staticmethod
    def compile_all(config: Config, py_files: list[str]) -> None:
        """Compile all source files in ``target_dir`` that need to be compiled.

        Uses ``os.chdir`` to switch to ``target_dir`` before compiling.
        ``target_dir`` is the project root (no ``__init__.py``), so Cython
        does not prepend a package name; ``--inplace`` places the generated
        ``.so`` files directly into the corresponding subdirectories.

        Args:
            config: The compilation configuration.
            py_files: List of file paths relative to ``target_dir``.
        """
        origin_cwd = os.getcwd()

        # Switch the working directory to ``target_dir``.
        os.chdir(config.target_dir)

        try:
            setup(
                ext_modules=cythonize(
                    module_list=py_files,
                    quiet=True,
                    compiler_directives=COMPILER_DIRECTIVES,
                ),
                script_args=["build_ext", "--inplace"],
            )
        finally:
            os.chdir(origin_cwd)

    @staticmethod
    def cleanup(config: Config, py_files: list[str]) -> None:
        """Remove intermediate build artifacts.

        Cleanup includes:
            - ``.c`` files (Cython intermediate artifacts).
            - Original source files (already compiled into ``.so``).
            - The ``build`` directory under ``target_dir``.
            - All ``__pycache__`` directories.

        Args:
            config: The compilation configuration.
            py_files: List of compiled file paths relative to ``target_dir``.
        """
        # Remove the ``.c`` file and the source file for each compiled file.
        for rel_path_str in py_files:
            rel_path = Path(rel_path_str)
            abs_path = config.target_dir / rel_path

            # Remove the ``.c`` intermediate file.
            c_file = abs_path.with_suffix(".c")
            if c_file.is_file():
                c_file.unlink()

            # Remove the original source file (``.py`` / ``.pyx`` / ``.pyw``).
            if abs_path.is_file():
                abs_path.unlink()

        # Remove the ``build`` directory under ``target_dir``.
        # Using Path's "/" operator to join paths is safe on all platforms.
        build_dir = config.target_dir / "build"
        if build_dir.is_dir():
            shutil.rmtree(build_dir)

        # Remove all ``__pycache__`` directories.
        for pycache in config.target_dir.rglob("__pycache__"):
            if pycache.is_dir():
                shutil.rmtree(pycache)

    # ------------------------------------------------------------------
    # Main workflow
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Run the full compile-and-encrypt workflow."""
        # Load the configuration.
        config = self.load_config()
        logger.info("[1/4] Configuration loaded")
        logger.info("      Source directory: %s", config.source_dir)
        logger.info("      Target directory: %s", config.target_dir)

        # Step 2.1 - Copy.
        self.copy_source_dir(config)
        logger.info("[2/4] Directory copy complete")

        # Step 2.2 - Scan files to compile.
        py_files = self.find_compile_files(config)
        logger.info("[3/4] Scan complete, %d files to compile", len(py_files))
        for f in py_files:
            logger.info("      - %s", f)

        if not py_files:
            logger.info("No files to compile")
            return

        # Step 2.3 - Compile.
        logger.info("[4/4] Compiling...")
        self.compile_all(config, py_files)
        logger.info("      Compilation complete")

        # Step 2.4 - Clean up intermediate artifacts.
        self.cleanup(config, py_files)
        logger.info("      Cleanup complete")

        logger.info("Done!")
