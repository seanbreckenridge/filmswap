import discord

from typing_extensions import TypeVar

ClientT = TypeVar(
    "ClientT", bound=discord.Client, covariant=True, default=discord.Client
)
