from __future__ import annotations
from logzero import logger

import discord
import discord.abc
from discord.ext import commands

from .db import (
    Swap,
    SwapPeriod,
    check_active_user,
    review_my_gift_embed,
    review_my_letter_embed,
    receive_gift_embed,
    get_santa,
    get_giftee,
    read_giftee_letter,
    set_gift,
    user_has_letter,
    set_gift_done,
    set_letter,
    leave_swap,
    has_giftee,
)
from .settings import settings
from .manage import Manage, JoinSwapButton


def help_embed() -> discord.Embed:
    embed = discord.Embed(title="Help", description="Filmswap Help")
    embed.add_field(
        name=">letter",
        value="Set your letter, which your Santa will see. This should include what kinds of films you like/dislike, and can include your accounts on letterboxd/imdb if you have one.",
        inline=False,
    )
    embed.add_field(
        name=">submit",
        value="Submit your gift/film-recommendation to your giftee",
        inline=False,
    )
    embed.add_field(
        name="/read",
        value="Read your letter from your giftee. After you picked something, >submit",
        inline=False,
    )
    embed.add_field(
        name="/receive",
        value="Read your gift from your Santa. After you've finished watching, /done-watching",
        inline=False,
    )
    embed.add_field(
        name="/review-letter",
        value="Review your current letter",
        inline=True,
    )
    embed.add_field(
        name="/review-gift",
        value="Review the gift you submitted",
        inline=True,
    )
    embed.add_field(
        name=">write-santa",
        value="Write an anonymous letter to your Santa",
        inline=True,
    )
    embed.add_field(
        name=">write-giftee",
        value="Write an anonymous letter to your giftee",
        inline=True,
    )
    embed.add_field(
        name="/done-watching",
        value="Mark your gift as watched",
        inline=True,
    )
    embed.add_field(
        name="/help",
        value="Show this help message",
        inline=True,
    )
    embed.add_field(
        name="/leave",
        value="Leave the filmswap, if you're currently in it",
        inline=True,
    )
    return embed


def create_bot() -> discord.Client:
    intents = discord.Intents.default() | discord.Intents(reactions=True)
    bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

    async def error_if_not_in_dm(ctx: discord.Interaction | commands.Context) -> bool:
        if isinstance(ctx, commands.Context):
            if ctx.guild is not None:
                await ctx.author.send(
                    "Hey, that command only works in DMs -- try using it here instead"
                )
                logger.info(
                    f"User {ctx.author.id} used command in guild, sending them a DM"
                )
                return True
        else:
            assert isinstance(ctx, discord.Interaction)
            if ctx.guild is not None:
                await ctx.response.send_message(
                    "This command only works in DMs -- try direct messaging this bot instead",
                    ephemeral=True,
                )
                logger.info(
                    f"User {ctx.user.id} used command in guild, telling them to use in DM instead"
                )
                return True
        return False

    async def not_active_user(ctx: discord.Interaction | commands.Context) -> bool:
        """
        returns True if user is not active, False if user is active
        """
        if isinstance(ctx, commands.Context):
            if error := check_active_user(ctx.author.id):
                await ctx.reply(error)
                return True
        else:
            assert isinstance(ctx, discord.Interaction)
            if error := check_active_user(ctx.user.id):
                await ctx.response.send_message(error, ephemeral=True)
                return True
        return False

    @bot.tree.command(name="review-letter", description="Review your letter")
    async def review_letter(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} reviewing their own letter")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        embed = review_my_letter_embed(interaction.user.id)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(
        name="letter-help",
        description="Write the letter your santa will see. Use >letter [text] instead",
    )
    async def letter_help(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used letter")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        await interaction.response.send_message(
            "Use `>letter [text]` to set your letter, where [text] is what kinds of films you like/dislike/want from your santa",
            ephemeral=True,
        )

    @bot.tree.command(
        name="write-santa",
        description="Write an anonymous letter to your santa. Use >write-santa [text] instead",
    )
    async def write_santa(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used write-santa")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        await interaction.response.send_message(
            "Use >write-santa [text] to set your letter, where [text] is what you want to say to your santa",
            ephemeral=True,
        )

    @bot.tree.command(
        name="write-giftee",
        description="Write an anonymous letter to your giftee. Use >write-giftee [text] instead",
    )
    async def write_giftee(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used write-giftee")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        await interaction.response.send_message(
            "Use >write-giftee [text] to set your letter, where [text] is what you want to say to your giftee",
            ephemeral=True,
        )

    @bot.tree.command(name="review-gift", description="Review your gift")
    async def review_gift(interaction: discord.Interaction):
        logger.info(
            f"User {interaction.user.id} viewing their own gift (the one they submitted)"
        )

        if await not_active_user(interaction):
            return

        embed = review_my_gift_embed(interaction.user.id)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(
        name="submit-help",
        description="Submit gift for your giftee (your recommendation). Use >submit instead",
    )
    async def submit_help(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} submitting gift")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        # prompt the user to set their gift
        await interaction.response.send_message(
            "Use `>submit [text]` to submit your gift, where [text] is your gift/film recommendation"
        )

    @bot.tree.command(name="receive", description="Read the gift from your Santa")
    async def receive(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used receive")

        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        gift = receive_gift_embed(interaction.user.id)
        await interaction.response.send_message(embed=gift, ephemeral=True)

    @bot.tree.command(name="read", description="Read the letter from your giftee")
    async def read(interaction: discord.Interaction):
        if await error_if_not_in_dm(interaction):
            return

        if await not_active_user(interaction):
            return

        logger.info(f"User {interaction.user.id} used read")

        letter = read_giftee_letter(interaction.user.id)
        await interaction.response.send_message(embed=letter, ephemeral=True)

    @bot.tree.command(name="leave", description="Leave the swap")
    async def leave(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used leave")

        if await error_if_not_in_dm(interaction):
            return

        if Swap.get_swap_period() != SwapPeriod.JOIN:
            logger.info(
                f"User {interaction.user.id} tried to leave the swap but it's not the JOIN period"
            )
            await interaction.response.send_message(
                "Sorry, you can't leave the swap right now. Wait till the beginning of the next swap period to leave",
                ephemeral=True,
            )
            return

        try:
            leave_swap(interaction.user.id)
        except RuntimeError as e:
            return await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

        await interaction.response.send_message(
            "You have left the swap. You can rejoin by clicking the 'join button' in the swap channel",
            ephemeral=True,
        )

    @bot.tree.command(name="done-watching", description="Mark your gift as watched")
    async def done_watching(interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} used done-watching")

        if await error_if_not_in_dm(interaction):
            return

        if Swap.get_swap_period() != SwapPeriod.WATCH:
            logger.info(
                f"User {interaction.user.id} tried to mark their gift as watched but it's not the WATCH period"
            )
            await interaction.response.send_message(
                "Can't set your gift as watched till the watch period starts",
                ephemeral=True,
            )
            return

        try:
            set_gift_done(interaction.user.id)
        except RuntimeError as e:
            return await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

        await interaction.response.send_message(
            "Your gift has been marked as watched", ephemeral=True
        )

    @bot.event
    async def on_command_error(ctx: commands.Context, error: Exception) -> None:
        logger.exception(f"Error: {error}", exc_info=True)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        await bot.process_commands(message)

        # these commands only work in DMs, so users can write out long paragraphs
        if (
            message.guild is not None
            or message.author.bot
            or message.author == bot.user
        ):
            return

        content = message.content.strip()
        if content.startswith(">letter"):
            logger.info(f"User {message.author.id} setting letter")

            if error := check_active_user(message.author.id):
                await message.author.send(error)
                return

            if Swap.get_swap_period() != SwapPeriod.JOIN:
                logger.info(
                    f"User {message.author.id} tried to set letter but it's not the JOIN period"
                )

                if user_has_letter(message.author.id):
                    # already has letter, check if they are allowed to change it right now
                    await message.author.send(
                        "Sorry, you can't change your letter right now. Wait till the beginning of the next swap to change it",
                    )
                    return

            letter_contents = content[len(">letter") :].strip()

            if not letter_contents:
                logger.info(
                    f"User {message.author.id} tried to set letter but didn't provide any text"
                )
                await message.author.send(
                    "Use `>letter [text]` to set your letter, where [text] is what kinds of films you like/dislike/want from your santa"
                )
                return

            logger.info(f"User {message.author.id} setting letter to {letter_contents}")

            set_letter(message.author.id, letter_contents)
            await message.reply("Your letter has been set, your santa will see:")
            await message.reply(embed=review_my_letter_embed(message.author.id))
        elif content.startswith(">submit"):
            logger.info(f"User {message.author.id} setting gift")

            if error := check_active_user(message.author.id):
                await message.author.send(error)
                return

            # check if they've already submitted a gift this swap
            # we should not allow people who have already submitted to change during the swap period,
            # but if they haven't submitted yet, they can submit at any time (to allow latecomers to join later)
            if Swap.get_swap_period() != SwapPeriod.SWAP:
                logger.info(
                    f"User {message.author.id} tried to set gift but it's not the SWAP period"
                )
                # already has gift, check if they are allowed to change it right now
                await message.author.send(
                    "Sorry, you can't change your gift right now. Wait till the next 'swap' period to set your gift",
                )
                return

            if not has_giftee(message.author.id):
                logger.info(
                    f"User {message.author.id} tried to set gift but they don't have a giftee"
                )
                await message.author.send(
                    "Sorry, you can't set your gift until you've been assigned a giftee",
                )
                return

            gift_contents = content[len(">submit") :].strip()

            if not gift_contents:
                logger.info(
                    f"User {message.author.id} tried to set gift but didn't provide any text"
                )
                await message.author.send(
                    "Use `>submit [text]` to submit your gift, where [text] is your gift/film recommendation"
                )
                return

            logger.info(f"User {message.author.id} setting gift to {gift_contents}")

            set_gift(message.author.id, gift_contents)
            await message.reply("Your gift has been sent, your giftee will see:")
            await message.reply(embed=review_my_gift_embed(message.author.id))

        elif content.startswith(">write-santa"):
            logger.info(f"User {message.author.id} sending message to santa")

            if error := check_active_user(message.author.id):
                await message.author.send(error)
                return

            santa = get_santa(message.author.id)

            if santa is None:
                logger.info(
                    f"User {message.author.id} tried to send message to santa but they don't have a santa"
                )
                await message.author.send(
                    "You can only send a message to your santa after you've been assigned one"
                )
                return

            message_contents = content[len(">write-santa") :].strip()

            if not message_contents:
                logger.info(
                    f"User {message.author.id} tried to send message to santa but didn't provide any text"
                )
                await message.author.send(
                    "Use >write-santa [text] to send a message to your santa, where [text] is your message"
                )
                return

            assert santa is not None
            assert isinstance(santa.user_id, int)
            santa_user = await bot.fetch_user(santa.user_id)

            if santa_user is None:
                logger.info(
                    f"User {message.author.id} tried to send message to santa but their santa's ID {santa.user_id} is invalid"
                )
                await message.author.send(
                    "There was an error messaging your santa, could not assosiate their ID with a discord account. Try again later or contact a mod to check on your santa"
                )
                return
            else:
                logger.info(
                    f"User {message.author.id} {message.author.display_name} sending message to santa {santa.user_id} {santa.name} {message_contents}"
                )
                embed = discord.Embed()
                embed.add_field(
                    name="Your giftee sent you a message", value=message_contents
                )
                await santa_user.send(embed=embed)

                await message.author.send("Your message has been sent")

        elif content.startswith(">write-giftee"):
            logger.info(f"User {message.author.id} sending message to giftee")

            if error := check_active_user(message.author.id):
                await message.author.send(error)
                return

            giftee = get_giftee(message.author.id)

            if giftee is None:
                logger.info(
                    f"User {message.author.id} tried to send message to giftee but they don't have a giftee"
                )
                await message.author.send(
                    "You can only send a message to your giftee after you've been assigned one"
                )
                return

            message_contents = content[len(">write-giftee") :].strip()

            if not message_contents:
                logger.info(
                    f"User {message.author.id} tried to send message to giftee but didn't provide any text"
                )
                await message.author.send(
                    "Use >write-giftee [text] to send a message to your giftee, where [text] is your message"
                )
                return

            assert giftee is not None
            assert isinstance(giftee.user_id, int)
            giftee_user = await bot.fetch_user(giftee.user_id)

            if giftee_user is None:
                logger.info(
                    f"User {message.author.id} tried to send message to giftee but their giftee's ID {giftee.user_id} is invalid"
                )
                await message.author.send(
                    "There was an error messaging your giftee, could not assosiate their ID with a discord account. Try again later or contact a mod to check on your giftee"
                )
                return
            else:
                logger.info(
                    f"User {message.author.id} {message.author.display_name} sending message to giftee {giftee.user_id} {giftee.name} {message_contents}"
                )
                embed = discord.Embed()
                embed.add_field(
                    name="Your santa sent you a message", value=message_contents
                )
                await giftee_user.send(embed=embed)
                await message.author.send("Your message has been sent")

    @bot.tree.command()
    async def help(interaction: discord.Interaction) -> None:
        logger.info(f"User {interaction.user.id} requested help")
        await interaction.response.send_message(embed=help_embed(), ephemeral=True)

    @bot.event
    async def setup_hook() -> None:
        logger.info("Setting up persistent join button")
        latest_swap_msg_id = Swap.get_join_button_message_id()
        if latest_swap_msg_id is None:
            logger.info("No join button message ID found")
        else:
            logger.info(f"Found saved button message ID: {latest_swap_msg_id}")
        bot.add_view(JoinSwapButton(), message_id=latest_swap_msg_id)

    @bot.event
    async def on_ready() -> None:
        logger.info(f"Logged in as {bot.user}")
        if settings.GUILD_ID == -1:
            logger.warning("No guild ID specified, cannot register commands")
            return
        guild = bot.get_guild(settings.GUILD_ID)
        if guild is None:
            logger.warning(
                f"Cannot find guild with ID {settings.GUILD_ID}, cannot register commands",
            )
            return

        manager = Manage(name="filmswap-manage", description="Manage swaps")
        manager._bot = bot  # type: ignore

        bot.tree.add_command(manager)
        bot.tree.copy_global_to(guild=discord.Object(id=settings.GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=settings.GUILD_ID))

        await bot.tree.sync()

    return bot
