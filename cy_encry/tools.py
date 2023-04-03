import json
import os
import re
import shutil
import traceback
from pathlib import Path
from setuptools import setup
from typing import List, Tuple

from Cython.Build import cythonize

# Cython 编译参数
COMPILER_DIRECTIVES = {
    'language_level': 3,
    'always_allow_keywords': True,
    'annotation_typing': False
}


class Config:
    def __init__(self, config_path: str) -> None:
        self.config_path = Path(config_path)

        # 源文件所在文件路径夹
        self.source_dir = None
        # 目标文件夹路径
        self.target_dir = None
        # 中间生成的 C 文件文件夹路径
        self.c_source_dir = None

        self.need_compile_dirs = list()

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

                for key, value in params.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

            if not self.source_dir:
                return False, f'{self.source_dir} is not a dir!'
            self.source_dir = Path(self.source_dir)

            self.target_dir = Path(str(self.source_dir.absolute()) + '_target')
            self.c_source_dir = Path(str(self.source_dir.absolute()) + '_c_source')
            if self.target_dir.is_dir():
                shutil.rmtree(self.target_dir)
            if self.c_source_dir.is_dir():
                shutil.rmtree(self.c_source_dir)

            return True, ''
        except Exception as exc:
            print(traceback.format_exc())
            return False, str(exc)


class Operator:
    def __init__(self, config: Config) -> None:
        """__init__

        Args:
            config (Config): 配置对象
        """

        self.config = config

        self.need_compile_rules = ('.py', 'pyx')
        self.exclude_compile_rules = ['__init__.py', '__init__.pyx']

        # 需要编译的源文件
        self.need_compile_paths = dict()

    def search_files(self):
        """搜索，查找符合处理条件的源文件，保存至列表
        """

        shutil.copytree(self.config.source_dir, self.config.target_dir)

        for one_dir in self.config.need_compile_dirs:
            abs_dir = os.path.join(self.config.target_dir, one_dir)
            abs_dir_p = Path(abs_dir)

            lis = list()

            for name in os.listdir(abs_dir):
                if str(name) in self.exclude_compile_rules:
                    continue

                if str(name).endswith(self.need_compile_rules):
                    lis.append(name)

            self.need_compile_paths[abs_dir_p] = lis

        print(self.need_compile_paths)

    def remove(self, parent_dir: Path):
        """清理，转移"""

        parent_dir_str = str(parent_dir).replace(str(self.config.target_dir), '').lstrip('/')
        c_source_parent_dir = self.config.c_source_dir.joinpath(parent_dir_str)
        c_source_parent_dir.mkdir(parents=True, exist_ok=True)
        target_parent_dir = self.config.target_dir.joinpath(parent_dir)
        temp_build_dir = parent_dir.joinpath('build')

        for name in os.listdir(parent_dir):
            # 转移 C 文件
            name = str(name)
            if name.endswith('.c'):
                shutil.move(parent_dir.joinpath(name), c_source_parent_dir.joinpath(name))

            # 转移并重命名动态链接库
            if name.endswith('.so') or name.endswith('.pyd'):
                new_filename = re.sub(r'(.*)\..*\.(.*)', r'\1.\2', name)
                shutil.move(parent_dir.joinpath(name), target_parent_dir.joinpath(new_filename))

            if name.endswith(self.need_compile_rules):
                os.remove(parent_dir.joinpath(name))

        # 删除临时 build 文件夹
        if temp_build_dir.is_dir():
            shutil.rmtree(temp_build_dir)

    def compile(self):

        for abs_dir, names in self.need_compile_paths.items():
            # 切换至目录
            p = Path(abs_dir)

            os.chdir(p)

            # 执行
            setup(
                ext_modules=cythonize(names, quiet=True, compiler_directives=COMPILER_DIRECTIVES)
            )

            self.remove(abs_dir)

    def execute(self):

        success, msg = self.config.init()
        print(success, msg)

        self.search_files()

        self.compile()


config = Config('./config.json')

op = Operator(config)

op.execute()
