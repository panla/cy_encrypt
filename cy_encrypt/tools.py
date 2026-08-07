import json
import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from setuptools import setup
from typing import Tuple, List, Dict

from Cython.Build import cythonize

# Cython 编译参数
COMPILER_DIRECTIVES = {
    'language_level': 3,
    'always_allow_keywords': True,
    # 'annotation_typing': False  # Cython 3.x 已移除该指令，注释保留
}


class Operator:
    def __init__(self, config_path: str) -> None:
        """__init__

        Args:
            config_path (str): 配置文件路径
        """

        self.need_compile_rules = '.py'
        self.exclude_compile_rules = ['__init__.py']

        self.config_path = Path(config_path)

        # 来自配置文件
        # 源文件所在文件夹路径
        self.source_dir = Path('')
        # 跳过不编译的文件夹（相对 source_dir 的路径）
        self.skip_dirs = list()
        # 复制时跳过的文件夹/文件（相对 source_dir 的路径）
        self.skip_cp_dirs = list()

        # 目标文件夹路径
        self.target_dir = Path('')

        # 需要编译的文件 父路径 -> [文件名列表]
        self.need_compile_map: Dict[Path, List[str]] = dict()

    @staticmethod
    def _rel_match(rel_path: Path, base_list: List[str]) -> bool:
        """判断相对路径是否匹配 base_list 中的某个路径（含其自身及其子路径）

        Args:
            rel_path (Path): 相对 source_dir 的路径
            base_list (List[str]): 需要匹配的路径列表

        Returns:
            bool: 是否匹配
        """

        for base in base_list:
            base_path = Path(base)
            if rel_path == base_path:
                return True
            try:
                rel_path.relative_to(base_path)
                return True
            except ValueError:
                pass
        return False

    def init(self) -> Tuple[bool, str]:
        """初始化解析配置文件

        Returns:
            Tuple[bool, str]: (success, info)
        """

        if not self.config_path.is_file():
            return False, f'配置文件 {self.config_path} is not a file'

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                params = json.load(f)

                source_dir = params.get('source_dir')
                skip_dirs = params.get('skip_dirs', list())
                skip_cp_dirs = params.get('skip_cp_dirs', list())

            if not source_dir:
                return False, f'{source_dir} is not exist!'
            self.source_dir = Path(source_dir)

            if not self.source_dir.is_dir():
                return False, f'{self.source_dir} is not a dir!'

            self.skip_dirs = skip_dirs
            self.skip_cp_dirs = skip_cp_dirs

            now = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
            self.target_dir = self.source_dir.parent.joinpath(self.source_dir.name + f'_{now}')

            return True, ''
        except Exception as exc:
            print(traceback.format_exc())
            return False, str(exc)

    def copy_files(self):
        """复制 source_dir 到 target_dir，保持相对路径不变，跳过 skip_cp_dirs
        """

        if self.target_dir.is_dir():
            shutil.rmtree(self.target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(self.source_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.source_dir)

            # 过滤掉 skip_cp_dirs 中的目录
            dirs[:] = [
                d for d in dirs
                if not self._rel_match(rel_root / d, self.skip_cp_dirs)
            ]

            for file in files:
                rel_file = rel_root / file
                # 过滤掉 skip_cp_dirs 中的文件
                if self._rel_match(rel_file, self.skip_cp_dirs):
                    continue

                src = root_path / file
                dst = self.target_dir / rel_file
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    def search_files(self):
        """搜索 target_dir 下需要编译的 .py 文件，按父目录分组保存
        """

        for root, dirs, files in os.walk(self.target_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.target_dir)

            # 过滤掉 skip_dirs 中的目录
            dirs[:] = [
                d for d in dirs
                if not self._rel_match(rel_root / d, self.skip_dirs)
            ]

            compile_names = list()
            for file in files:
                # 只编译 .py 文件
                if not file.endswith(self.need_compile_rules):
                    continue
                # 排除不需要编译的文件
                if file in self.exclude_compile_rules:
                    continue
                # 排除 skip_dirs 中的文件
                if self._rel_match(rel_root / file, self.skip_dirs):
                    continue
                compile_names.append(file)

            if compile_names:
                self.need_compile_map[root_path] = compile_names

    def remove(self, parent_dir: Path, names: List[str]):
        """清理编译产物：删除 .py、.c、build 和 __pycache__"""

        for name in names:
            # 删除中间生成的 C 文件
            c_name = name.replace('.py', '.c')
            c_file = parent_dir / c_name
            if c_file.is_file():
                os.remove(c_file)

            # 删除编译后的源文件
            os.remove(parent_dir / name)

        # 删除临时 build 文件夹
        build_dir = parent_dir / 'build'
        if build_dir.is_dir():
            shutil.rmtree(build_dir)

        # 删除 __pycache__ 文件夹
        pycache_dir = parent_dir / '__pycache__'
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)

    def compile(self):
        """编译 .py 文件为动态链接库，保持相对路径不变"""

        for abs_path_p, names in self.need_compile_map.items():
            # 切换至该目录编译，保证编译出的模块导入路径正确
            os.chdir(abs_path_p)
            try:
                setup(
                    ext_modules=cythonize(
                        names,
                        quiet=True,
                        compiler_directives=COMPILER_DIRECTIVES
                    ),
                    script_args=['build_ext', '--inplace']
                )
            finally:
                # 编译完成后切回目标目录
                os.chdir(self.target_dir)

            self.remove(abs_path_p, names)

    def execute(self):

        success, msg = self.init()
        if not success:
            raise Exception(msg)

        self.copy_files()

        self.search_files()

        self.compile()
