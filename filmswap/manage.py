from __future__ import annotations
import io
import os
from pathlib import Path
from typing import Literal

import networkx as nx  # type: ignore[import]
import matplotlib.pyplot as plt  # type: ignore[import]

import discord
from discord.ext import commands

from logzero import logger  # type: ignore[import]

from .settings import settings
from .db import (
    snapshot_database,
    Session,
    SwapPeriod,
    Swap,
    Banned,
    read_giftee_letter,
    receive_gift_embed,
    ban_user,
    unban_user,
    join_swap,
    set_gift_done,
    engine,
    SwapUser,
)

DISABLE_UNMATCH = True


def list_users() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).all()  # type: ignore[no-any-return]


def havent_set_letter() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).filter_by(letter=None).all()  # type: ignore[no-any-return]


def havent_submitted_gift() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).filter_by(gift=None).all()  # type: ignore[no-any-return]


def users_without_giftees() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).filter_by(giftee_id=None).all()  # type: ignore[no-any-return]


def users_without_santas() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).filter_by(santa_id=None).all()  # type: ignore[no-any-return]


def users_not_done_watching() -> list[SwapUser]:
    with Session(engine) as session:  # type: ignore[attr-defined]
        return session.query(SwapUser).filter_by(done_watching=False).all()  # type: ignore[no-any-return]


class JoinSwapButton(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    def get_bot(self) -> commands.Bot:
        assert hasattr(self, "_bot")
        assert isinstance(self._bot, commands.Bot)  # type: ignore
        return self._bot  # type: ignore

    @property
    def swap_role_id(self) -> int:
        resp = self.get_bot().filmswap_role_id()  # type: ignore
        assert isinstance(resp, int)
        return resp

    @discord.ui.button(
        label="Join swap",
        style=discord.ButtonStyle.primary,
        custom_id="filmswap:join_swap",
    )
    async def join_swap(
        self, interaction: discord.Interaction, button: discord.ui.Button  # type: ignore[type-arg]
    ) -> None:
        logger.info(
            f"User {interaction.user.id} {interaction.user.display_name} clicked button to join swap"
        )

        # shared function which is called to give role to user, regardless of whether or not
        # they actually joined. this is so that they are notified next time, if they tried to join
        async def _add_role() -> None:
            logger.info(
                f"Giving user {interaction.user.id} {interaction.user.name} role"
            )
            # this has to be done in a server
            assert interaction.guild is not None
            assert isinstance(interaction.user, discord.Member)

            # add the film role swap to the user
            await interaction.user.add_roles(
                discord.Object(self.swap_role_id), reason="User joined film swap"
            )

        try:
            join_swap(interaction.user.id, interaction.user.display_name)
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            await _add_role()
            self.is_finished()
            return

        await interaction.user.send(
            "You've joined the swap. You can now submit a >letter, which should be a message which tells your santa what kinds of films you like/dislike, and can include your accounts on letterboxd/imdb if you have one."
        )

        await interaction.response.send_message(
            "Joined swap. Check your DMs to set your letter",
            ephemeral=True,
        )

        await _add_role()

        self.is_finished()


# returns True if this errored
async def error_if_not_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or interaction.guild.id != settings.GUILD_ID:
        logger.info(
            f"User {interaction.user.id} {interaction.user.display_name} tried to use admin command in DMs"
        )
        await interaction.response.send_message(
            "This command can only be used in a server", ephemeral=True
        )
        return True

    assert isinstance(interaction.user, discord.Member)

    if (
        interaction.user.guild_permissions
        and interaction.user.guild_permissions.administrator
    ):
        logger.info(
            f"User {interaction.user.id} {interaction.user.display_name} is admin in server, allowing"
        )
        return False

    allowed = any(
        role.name in settings.ALLOWED_ROLES for role in interaction.user.roles
    )
    if not allowed:
        logger.info(
            f"User {interaction.user.id} {interaction.user.display_name} does not have any matching roles, not allowing"
        )
        await interaction.response.send_message(
            "You don't have permission to use this command", ephemeral=True
        )
        return True
    return False


# create group to manage swaps
class Manage(discord.app_commands.Group):
    def get_bot(self) -> commands.Bot:
        assert hasattr(self, "_bot")
        assert isinstance(self._bot, commands.Bot)  # type: ignore
        return self._bot  # type: ignore

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="create", description="Create the swap for this server"
    )
    async def create(self, interaction: discord.Interaction) -> None:
        if await error_if_not_admin(interaction):
            return

        try:
            Swap.create_swap()
            await interaction.response.send_message(
                "Created swap. Remember to /filmswap-manage set-channel to set the channel where the swap will take place",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

    async def _set_period_post_hook(
        self, interaction: discord.Interaction, successfully_set_to: SwapPeriod
    ) -> None:
        """
        This handles sending out the letters to users when the swap period is set to SWAP
        And sending the gifts when the swap period is set to WATCH

        This runs after the period is set/responding to the user, so even if it fails, users
        can still run /read, /receive themselves
        """

        if successfully_set_to == SwapPeriod.SWAP:
            with Session(engine) as session:  # type: ignore[attr-defined]
                users = session.query(SwapUser).all()
                for user in users:
                    logger.info(f"Sending {user.user_id} their giftees letter")
                    if user.giftee_id is None:
                        logger.info(
                            f"Cannot send letter to {user.user_id} {user.name} as they have no giftee id"
                        )
                        continue
                    try:
                        letter_embed = read_giftee_letter(user.user_id)

                        user_dm = await self.get_bot().fetch_user(user.user_id)
                        await user_dm.send(embed=letter_embed)
                    except Exception as e:
                        logger.exception(
                            f"Error sending letter to user {user.user_id}: {e}",
                            exc_info=True,
                        )
        elif successfully_set_to == SwapPeriod.WATCH:
            with Session(engine) as session:  # type: ignore[attr-defined]
                users = session.query(SwapUser).all()
                for user in users:
                    logger.info(f"Sending {user.user_id} their santas gift")
                    if user.giftee_id is None:
                        logger.info(
                            f"Cannot send gift to {user.user_id} {user.name} as they have no giftee id"
                        )
                        continue
                    try:
                        gift_embed = receive_gift_embed(user.user_id)

                        user_dm = await self.get_bot().fetch_user(user.user_id)
                        await user_dm.send(embed=gift_embed)
                    except Exception as e:
                        logger.exception(
                            f"Error sending gift to user {user.user_id}: {e}",
                            exc_info=True,
                        )

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="set-period",
        description="Set the period of the swap (e.g. join, swap, watch))",
    )
    async def set_period(self, interaction: discord.Interaction, period: str) -> None:
        logger.info(f"Setting period of swap to {period}")

        if await error_if_not_admin(interaction):
            return

        assert isinstance(interaction.channel, discord.TextChannel)

        try:
            new_period = SwapPeriod[period.upper()]
            logger.info(f"Setting period to {new_period}")
        except KeyError:
            await interaction.response.send_message(
                f"Error: {period} is not a valid period", ephemeral=True
            )
            return

        try:
            additional_message = Swap.set_swap_period(new_period)
        except Exception as e:
            logger.exception(e, exc_info=True)
            return await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

        msg = f"Set period for swap to {period}"
        if additional_message is not None:
            msg += f"\n{additional_message}"

        await interaction.response.send_message(msg, ephemeral=True)
        await self._set_period_post_hook(interaction, new_period)

    @set_period.autocomplete("period")
    async def set_period_autocomplete_period(
        self, interaction: discord.Interaction, current: str
    ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(name=period.capitalize(), value=period)
            for period in SwapPeriod.__members__
            if period.lower().startswith(current.lower())
        ]

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="match-users",
        description="Match all users. Requires at least 2 unmatched users, can be run later to match latecomers",
    )
    async def match_users(self, interaction: discord.Interaction) -> None:
        if await error_if_not_admin(interaction):
            return

        logger.info(f"Admin {interaction.user.id} matching users")

        try:
            Swap.match_users()
        except Exception as e:
            logger.exception(e, exc_info=True)
            return await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

        await interaction.response.send_message("Matched all users", ephemeral=True)

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="unmatch-users",
        description="Unmatch all users the swap. This wont delete gifts/letters, just remove all connections",
    )
    async def unmatch_users(self, interaction: discord.Interaction) -> None:
        """
        This is mostly a debug command, in case things go wrong
        """
        if await error_if_not_admin(interaction):
            return

        if DISABLE_UNMATCH:
            return await interaction.response.send_message(
                "Unmatching users is disabled", ephemeral=True
            )

        logger.info(f"Admin {interaction.user.id} unmatching users")

        try:
            Swap.unmatch_users()
        except Exception as e:
            logger.exception(e, exc_info=True)
            return await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

        await interaction.response.send_message("Unmatched all users", ephemeral=True)

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="set-channel",
        description="Set the channel where the swap will take place",
    )
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        logger.info(f"Setting channel for swap to {channel}")

        try:
            Swap.set_swap_channel(channel.id)
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Set channel for swap to {channel} {channel.id}", ephemeral=True
        )

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="send-join-message",
        description="Send a message to the channel so people can join the swap",
    )
    async def send_join_message(self, interaction: discord.Interaction) -> None:
        logger.info("Sending message to channel so people can join")

        if await error_if_not_admin(interaction):
            return

        try:
            swap_info = Swap.get_swap()
            if swap_info.swap_channel_discord_id is None:
                logger.info("No channel set for swap")
                await interaction.response.send_message(
                    "Error: No channel set for swap", ephemeral=True
                )
                return
            bot = self.get_bot()
            channel = await bot.fetch_channel(swap_info.swap_channel_discord_id)

            assert isinstance(channel, discord.TextChannel)
            view = JoinSwapButton()
            view._bot = self.get_bot()  # type: ignore
            msg = await channel.send(
                "Join the film swap by clicking the button below!",
                view=view,
            )

            # save this so that it can become a persistent view
            Swap.save_join_button_message_id(msg.id)

            await interaction.response.send_message(
                f"Sent message to channel {channel}", ephemeral=True
            )

        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="filmswap-ban", description="Ban a user from the swap"
    )
    async def filmswap_ban(
        self, interaction: discord.Interaction, discord_user_id: str
    ) -> None:
        if await error_if_not_admin(interaction):
            return

        logger.info(f"Admin {interaction.user.id} banning user {discord_user_id}")

        try:
            user_id = int(discord_user_id)
        except ValueError:
            await interaction.response.send_message(
                f"Error: {discord_user_id} is not an integer", ephemeral=True
            )
            return

        if Swap.get_swap_period() != SwapPeriod.JOIN:
            logger.info("Can only ban users during the join period")
            await interaction.response.send_message(
                "Error: Can only ban users during the join period", ephemeral=True
            )
            return

        assert interaction.guild is not None

        try:
            ban_user(user_id)
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Banned {user_id} from the swap", ephemeral=True
        )

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="filmswap-unban", description="Unban a user from the swap"
    )
    async def filmswap_unban(
        self, interaction: discord.Interaction, discord_user_id: str
    ) -> None:
        if await error_if_not_admin(interaction):
            return

        logger.info(f"Admin {interaction.user.id} unbanning user {discord_user_id}")

        try:
            user_id = int(discord_user_id)
        except ValueError:
            await interaction.response.send_message(
                f"Error: {discord_user_id} is not an integer", ephemeral=True
            )
            return

        if Swap.get_swap_period() != SwapPeriod.JOIN:
            logger.info("Can only unban users during the join period")
            await interaction.response.send_message(
                "Error: Can only unban users during the join period",
                ephemeral=True,
            )
            return

        assert interaction.guild is not None

        try:
            unban_user(user_id)
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Unbanned {user_id} from the swap", ephemeral=True
        )

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="set-user-done-watching", description="Set /done-watching for a user"
    )
    async def set_watching(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        logger.info(f"Admin setting done watching for {member.id}")

        if await error_if_not_admin(interaction):
            return

        try:
            set_gift_done(member.id)
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Set done watching for {member.display_name}", ephemeral=True
        )

    @discord.app_commands.command(name="info", description="Get info about the swap")  # type: ignore[arg-type]
    async def info(self, interaction: discord.Interaction) -> None:
        logger.info("Getting info for swap")

        if await error_if_not_admin(interaction):
            return

        try:
            swap = Swap.get_swap()
        except Exception as e:
            logger.exception(e, exc_info=True)
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            return

        embed = discord.Embed(title="Swap")
        assert isinstance(swap.period, SwapPeriod)
        embed.add_field(
            name="Period", value=swap.period.name if swap.period else "None"
        )
        bot = self.get_bot()
        assert swap.swap_channel_discord_id is not None
        channel = bot.get_channel(swap.swap_channel_discord_id)
        assert isinstance(channel, discord.TextChannel) or channel is None
        embed.add_field(name="Channel", value=channel.mention if channel else "None")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        all_users = list_users()
        no_letters = havent_set_letter()
        havent_submitted = havent_submitted_gift()
        dont_have_parters = users_without_giftees()
        dont_have_santas = users_without_santas()
        not_done_watching = users_not_done_watching()
        banned = Banned.list_banned()

        report = f"""**{len(all_users)}** users are in the swap

{os.linesep.join(f'{user.user_id} {user.name}' for user in all_users)}

**{len(no_letters)}** users have not submitted letters

{os.linesep.join(f'{user.user_id} {user.name}' for user in no_letters)}

**{len(havent_submitted)}** users have not submitted gifts

{os.linesep.join(f'{user.user_id} {user.name}' for user in havent_submitted)}

**{len(not_done_watching)}** users have not set /done-watching

{os.linesep.join(f'{user.user_id} {user.name}' for user in not_done_watching)}

**{len(dont_have_parters)}** users do not have giftees

{os.linesep.join(f'{user.user_id} {user.name}' for user in dont_have_parters)}

**{len(dont_have_santas)}** users do not have santas

{os.linesep.join(f'{user.user_id} {user.name}' for user in dont_have_santas)}

**{len(banned)}** users are banned

{os.linesep.join(f'{user.user_id}' for user in banned)}
"""

        with io.BytesIO() as f:
            f.write(report.encode("utf-8"))
            f.seek(0)
            await interaction.user.send(file=discord.File(f, "report.txt"))

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="reveal", description="Reveal the connections between giftee/santas"
    )
    async def reveal(
        self, interaction: discord.Interaction, format: Literal["text", "graph"]
    ) -> None:
        logger.info(f"User {interaction.user.id} revealing connections -- {format}")

        if await error_if_not_admin(interaction):
            return

        all_users = list_users()
        users_with_both = [
            user for user in all_users if user.giftee_id and user.santa_id
        ]

        if len(users_with_both) == 0:
            await interaction.response.send_message(
                "Error: No users have both a giftee and a santa", ephemeral=True
            )
            return

        id_to_names: dict[int, str] = {
            user.user_id: user.name for user in users_with_both
        }

        bot = self.get_bot()
        user_obj = await bot.fetch_user(interaction.user.id)

        if format == "text":
            report = os.linesep.join(
                f"{id_to_names.get(user.user_id, user.user_id)} is gifting to {id_to_names.get(user.giftee_id, user.giftee_id)} and is being gifted by {id_to_names.get(user.santa_id, user.santa_id)}"  # type: ignore[arg-type]
                for user in users_with_both
            )
            with io.BytesIO() as f:
                f.write(report.encode("utf-8"))
                f.seek(0)
                await interaction.user.send(file=discord.File(f, "report.txt"))

        else:
            graph = nx.DiGraph()
            plt.clf()
            for user in users_with_both:
                assert user.giftee_id is not None
                graph.add_edge(user.name, id_to_names[user.giftee_id], color="red")

            options = {
                "node_color": "blue",
                "node_size": 1,
                "edge_color": "grey",
                "font_size": 8,
                "width": 3,
                "arrowstyle": "-|>",
                "arrowsize": 12,
            }

            nx.draw_networkx(graph, arrows=True, **options)
            plt.box(False)
            with io.BytesIO() as f:
                plt.savefig(f, pad_inches=0.1, transparent=False, bbox_inches="tight")
                f.seek(0)
                await user_obj.send(file=discord.File(f, "reveal.png"))

        await interaction.response.send_message(
            f"Sent reveal to {interaction.user.display_name}", ephemeral=True
        )

    @discord.app_commands.command(  # type: ignore[arg-type]
        name="backup-db", description="Backup the database"
    )
    async def backup(self, interaction: discord.Interaction) -> None:
        logger.info(f"User {interaction.user.id} backing up database")

        if await error_if_not_admin(interaction):
            return

        snapshot_database()

        files = Path(settings.BACKUP_DIR).glob("*.sqlite")
        latest = max(files, key=os.path.getmtime)

        await interaction.response.send_message(
            f"Saved database backup to {latest.name}", ephemeral=True
        )
