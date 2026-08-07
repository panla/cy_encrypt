"""
cy_encrypt.cli
~~~~~~~~~~~~~~

命令行入口。
"""

import logging

import click

from cy_encrypt.tools import run
from cy_encrypt.version import __version__

# 配置日志 (默认输出格式)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.option(
    "-c",
    "--config",
    default="config.json",
    show_default=True,
    help="配置文件路径",
)
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """cy_encrypt - Python 源码编译加密工具"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command(help="执行编译加密流程")
@click.pass_context
def execute(ctx: click.Context) -> None:
    """执行完整的编译加密流程"""
    run(ctx.obj["config"])


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
