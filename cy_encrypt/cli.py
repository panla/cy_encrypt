import click
from click import Context

from cy_encrypt.version import __version__
from cy_encrypt.tools import Operator


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version")
@click.option(
    "-c",
    "--config",
    default="config.json",
    show_default=True,
    help="Config file.",
)
@click.pass_context
def cli(ctx: Context, config):

    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config

@cli.command(help="Execute.")
@click.pass_context
def execute(ctx: Context):
    """执行"""

    op = Operator(ctx.obj["config_file"])
    op.execute()


def main():
    cli()


if __name__ == "__main__":
    main()
