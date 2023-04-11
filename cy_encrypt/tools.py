import json
import os
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from setuptools import setup
from typing import Tuple, List

from Cython.Build import cythonize

# Cython 编译参数
COMPILER_DIRECTIVES = {
    'language_level': 3,
    'always_allow_keywords': True,
    'annotation_typing': False
}


class Operator:
    def __init__(self, config_path: str) -> None:
        """__init__

        Args:
            config_path (str): 配置文件路径
        """

        self.need_compile_rules = ('.py', 'pyx')
        self.exclude_compile_rules = ['__init__.py', '__init__.pyx']

        self.config_path = Path(config_path)

        # 来自配置文件
        # 源文件所在文件路径夹
        self.source_dir = Path('')
        # 需要编译的文件夹
        self.need_compile_paths = list()

        # 目标文件夹路径
        self.target_dir = Path('')
        # 中间生成的 C 文件文件夹路径
        self.c_source_dir = Path('')

        # 需要编译的源文件 父路径与本文件的 字典
        self.need_compile_map = dict()

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
                need_compile_paths = params.get('need_compile_paths', list())

            if not source_dir:
                return False, f'{self.source_dir} is not exist!'
            self.source_dir = Path(source_dir)

            if not self.source_dir.is_dir():
                return False, f'{self.source_dir} is not a dir!'

            if not need_compile_paths:
                return False, f'{need_compile_paths} is not exist!'

            self.need_compile_paths = need_compile_paths

            now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            self.target_dir = self.source_dir.parent.joinpath(self.source_dir.name + f'_target_{now}')
            self.c_source_dir = self.source_dir.parent.joinpath(self.source_dir.name + f'_c_source_{now}')

            return True, ''
        except Exception as exc:
            print(traceback.format_exc())
            return False, str(exc)

    def search_files(self):
        """搜索，查找符合处理条件的源文件，保存至列表
        """

        if not self.target_dir.is_dir():
            shutil.copytree(self.source_dir, self.target_dir)

        for path in self.need_compile_paths:
            abs_path_p = self.target_dir.joinpath(path)

            lis = list()

            if abs_path_p.is_dir():
                for name in os.listdir(abs_path_p):
                    name_str = str(name)
                    if name_str in self.exclude_compile_rules:
                        continue

                    if name_str.endswith(self.need_compile_rules):
                        lis.append(name_str)
                self.need_compile_map[abs_path_p] = lis
            elif abs_path_p.is_file():
                # 项目根目录
                lis.append(path)
                self.need_compile_map[self.target_dir] = lis

    def remove(self, parent_dir: Path, names: List[str]):
        """清理，转移"""

        if parent_dir.name != self.target_dir.name:
            c_source_parent_dir = self.c_source_dir.joinpath(parent_dir.name)
        else:
            c_source_parent_dir = self.c_source_dir.joinpath('')
        c_source_parent_dir.mkdir(parents=True, exist_ok=True)
        target_parent_dir = self.target_dir.joinpath(parent_dir)
        temp_build_dir = parent_dir.joinpath('build')

        for name in names:

            # 转移 C 文件
            c_name = name.replace('.pyx', '.c').replace('.py', '.c')
            if os.path.isfile(c_name):
                shutil.move(parent_dir.joinpath(c_name), c_source_parent_dir.joinpath(c_name))

            if name.endswith(self.need_compile_rules):
                os.remove(parent_dir.joinpath(name))

        for name in os.listdir(parent_dir):
            name_str = str(name)
            # 转移并重命名动态链接库
            if name_str.endswith(('.so', '.pyd')):
                new_filename = re.sub(r'(.*)\..*\.(.*)', r'\1.\2', name_str)
                shutil.move(parent_dir.joinpath(name_str), target_parent_dir.joinpath(new_filename))

            if '__pycache__' in name_str:
                shutil.rmtree('__pycache__')

        # 删除临时 build 文件夹
        if temp_build_dir.is_dir():
            shutil.rmtree(temp_build_dir)

    def compile(self):

        for abs_path_p, names in self.need_compile_map.items():
            # 切换至目录
            os.chdir(abs_path_p)

            # 执行
            setup(
                ext_modules=cythonize(names, quiet=True, compiler_directives=COMPILER_DIRECTIVES),
                script_args=['build_ext', '--inplace']
            )

            self.remove(abs_path_p, names)

            os.chdir(self.target_dir)

    def execute(self):

        success, msg = self.init()
        if not success:
            raise Exception(msg)

        self.search_files()

        self.compile()
