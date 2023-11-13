import asyncio

import click

from .bot import create_bot


@click.group()
def main() -> None:
    pass


async def _run_main(token: str) -> None:
    bot = create_bot()
    await bot.start(token=token, reconnect=True)


@main.command(short_help="run")
@click.option("--token", envvar="FILMSWAP_TOKEN", required=True)
def run(token: str) -> None:
    asyncio.run(_run_main(token=token))


if __name__ == "__main__":
    main(prog_name="filmswap")
