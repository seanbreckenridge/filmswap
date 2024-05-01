import asyncio

import click

from .bot import create_bot
from .settings import settings


@click.group()
def main() -> None:
    pass


async def _run_main(token: str) -> None:
    bot = create_bot()
    await bot.start(token=token, reconnect=True)


@main.command(short_help="run")
def run() -> None:
    if not settings.FILMSWAP_TOKEN:
        raise click.ClickException("FILMSWAP_TOKEN is not set")
    asyncio.run(_run_main(token=settings.FILMSWAP_TOKEN))


if __name__ == "__main__":
    main(prog_name="filmswap")
