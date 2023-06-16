import click

from .bot import create_bot


@click.group()
def main() -> None:
    pass


@main.command(short_help="run")
@click.option("--token", envvar="FILMSWAP_TOKEN", required=True)
def run(token: str) -> None:
    bot = create_bot()
    bot.run(token=token, reconnect=True)


if __name__ == "__main__":
    main(prog_name="filmswap")
