"""
cy_encrypt.tools
~~~~~~~~~~~~~~~~

将 Python 源码编译为 Cython 动态库 (.so/.pyd)。

流程:
    1. 将 source_dir 复制到 source_dir_YYYY_MM_DD_HH_MM_SS (skip_cp_dirs 不复制)
    2. 在 target_dir 中逐文件夹、逐文件筛选需要编译的 .py 文件
    3. 按目录分组编译，编译后删除中间产物 (.c / build / __pycache__ / 原 .py)
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from Cython.Build import cythonize
from setuptools import setup

# Cython 编译参数
COMPILER_DIRECTIVES: dict[str, Any] = {
    "language_level": 3,
    "always_allow_keywords": True,
}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
class Config:
    """编译配置"""

    source_dir: Path
    target_dir: Path
    skip_cp_dirs: list[str]
    skip_dirs: list[str]

    def __init__(
        self,
        source_dir: Path,
        target_dir: Path,
        skip_cp_dirs: list[str] | None = None,
        skip_dirs: list[str] | None = None,
    ) -> None:
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.skip_cp_dirs = skip_cp_dirs or []
        self.skip_dirs = skip_dirs or []


def load_config(config_path: Path) -> Config:
    """解析 JSON 配置文件并返回 Config 对象

    Args:
        config_path: 配置文件路径

    Returns:
        Config 对象

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置项缺失或无效
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        params = json.load(f)

    source_dir_str = params.get("source_dir")
    if not source_dir_str:
        raise ValueError("配置项 source_dir 缺失")

    source_dir = Path(source_dir_str).resolve()
    if not source_dir.is_dir():
        raise ValueError(f"source_dir 不是有效目录: {source_dir}")

    # 目标目录: 源目录名_时间戳, 位于源目录的父目录下
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    target_dir = source_dir.parent / f"{source_dir.name}_{timestamp}"

    return Config(
        source_dir=source_dir,
        target_dir=target_dir,
        skip_cp_dirs=params.get("skip_cp_dirs", []),
        skip_dirs=params.get("skip_dirs", []),
    )


# ---------------------------------------------------------------------------
# 路径匹配工具
# ---------------------------------------------------------------------------
def _match_skip(rel_path: PurePosixPath, skip_list: list[str]) -> bool:
    """判断相对路径是否命中 skip_list (命中自身或其父路径)

    Args:
        rel_path: 相对路径 (POSIX 风格)
        skip_list: 跳过路径列表

    Returns:
        True 表示应跳过
    """
    for pattern in skip_list:
        base = PurePosixPath(pattern)
        if rel_path == base or base in rel_path.parents:
            return True
    return False


def _need_compile(rel_path: PurePosixPath, skip_dirs: list[str]) -> bool:
    """判断文件是否需要编译

    规则:
        - 仅 .py 文件
        - 排除 __init__.py
        - 排除 skip_dirs 中的路径

    Args:
        rel_path: 相对 target_dir 的文件路径
        skip_dirs: 跳过目录列表

    Returns:
        True 表示需要编译
    """
    if rel_path.suffix != ".py":
        return False
    if rel_path.name == "__init__.py":
        return False
    return not _match_skip(rel_path, skip_dirs)


# ---------------------------------------------------------------------------
# 2.1 复制
# ---------------------------------------------------------------------------
def copy_source_dir(config: Config) -> None:
    """将 source_dir 复制到 target_dir, 跳过 skip_cp_dirs

    Args:
        config: 编译配置
    """
    # 如果目标目录已存在则清空
    if config.target_dir.exists():
        shutil.rmtree(config.target_dir)
    config.target_dir.mkdir(parents=True)

    for root, dirs, files in os.walk(config.source_dir):
        # 计算相对路径
        rel_root = PurePosixPath(os.path.relpath(root, config.source_dir))

        # 过滤需跳过的子目录 (原地修改 dirs 影响 os.walk 遍历)
        dirs[:] = [
            d for d in dirs
            if not _match_skip(rel_root / d, config.skip_cp_dirs)
        ]

        # 复制文件
        for name in files:
            file_rel = rel_root / name
            if _match_skip(file_rel, config.skip_cp_dirs):
                continue

            src = Path(root) / name
            dst = config.target_dir / file_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# 2.2 扫描需编译文件
# ---------------------------------------------------------------------------
def find_compile_files(config: Config) -> list[str]:
    """在 target_dir 中扫描需要编译的 .py 文件

    Args:
        config: 编译配置

    Returns:
        相对于 target_dir 的文件路径列表 (POSIX 风格, 如 "utils/helper.py")
    """
    result: list[str] = []

    for root, dirs, files in os.walk(config.target_dir):
        rel_root = PurePosixPath(os.path.relpath(root, config.target_dir))

        # 过滤跳过的子目录
        dirs[:] = [
            d for d in dirs
            if not _match_skip(rel_root / d, config.skip_dirs)
        ]

        # 收集需要编译的文件
        for name in files:
            file_rel = rel_root / name
            if _need_compile(file_rel, config.skip_dirs):
                result.append(str(file_rel))

    return result


# ---------------------------------------------------------------------------
# 2.3 编译 + 清理
# ---------------------------------------------------------------------------
def compile_all(config: Config, py_files: list[str]) -> None:
    """编译 target_dir 中所有需要编译的 .py 文件

    使用 os.chdir 切换到 target_dir 执行编译。
    target_dir 是项目根目录 (无 __init__.py), Cython 不会添加包名前缀,
    --inplace 直接将 .so 生成到对应子目录中。

    Args:
        config: 编译配置
        py_files: 相对于 target_dir 的文件路径列表
    """
    origin_cwd = os.getcwd()

    # 2.4 切换工作目录到 target_dir
    os.chdir(config.target_dir)

    try:
        setup(
            ext_modules=cythonize(
                py_files,
                quiet=True,
                compiler_directives=COMPILER_DIRECTIVES,
            ),
            script_args=["build_ext", "--inplace"],
        )
    finally:
        os.chdir(origin_cwd)


def cleanup(config: Config, py_files: list[str]) -> None:
    """清理编译中间产物

    清理内容:
        - .c 文件 (Cython 中间产物)
        - 原始 .py 文件 (已编译为 .so)
        - target_dir 下的 build 目录
        - 所有 __pycache__ 目录

    Args:
        config: 编译配置
        py_files: 已编译的相对路径文件列表
    """
    # 删除每个已编译文件对应的 .c 和 .py
    for rel_path_str in py_files:
        rel_path = Path(rel_path_str)
        abs_path = config.target_dir / rel_path

        # 删除 .c 中间产物
        c_file = abs_path.with_suffix(".c")
        if c_file.is_file():
            c_file.unlink()

        # 删除原始 .py 文件
        if abs_path.is_file():
            abs_path.unlink()

    # 删除 target_dir 下的 build 目录
    build_dir = config.target_dir / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir)

    # 删除所有 __pycache__ 目录
    for pycache in config.target_dir.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run(config_path: str) -> None:
    """执行完整的编译加密流程

    Args:
        config_path: 配置文件路径
    """
    # 加载配置
    config = load_config(Path(config_path))
    print(f"[1/4] 配置加载完成")
    print(f"      源目录: {config.source_dir}")
    print(f"      目标目录: {config.target_dir}")

    # 2.1 复制
    copy_source_dir(config)
    print(f"[2/4] 目录复制完成")

    # 2.2 扫描需编译文件
    py_files = find_compile_files(config)
    print(f"[3/4] 扫描完成, 共 {len(py_files)} 个文件待编译")
    for f in py_files:
        print(f"      - {f}")

    if not py_files:
        print("无需编译的文件")
        return

    # 2.3 编译
    print(f"[4/4] 编译中...")
    compile_all(config, py_files)
    print("      编译完成")

    # 2.4 清理中间产物
    cleanup(config, py_files)
    print("      清理完成")

    print("完成!")
