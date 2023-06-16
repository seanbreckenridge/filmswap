from __future__ import annotations
import random
import enum

import discord

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Enum,
)
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import MetaData
from logzero import logger


metadata = MetaData()
Base = declarative_base(metadata=metadata)

from .settings import settings


class SwapPeriod(enum.Enum):
    JOIN = "JOIN"
    SWAP = "SWAP"
    WATCH = "WATCH"


# probably just gonna be a singleton, run multiple instances of the bot for additional swaps
class Swap(Base):
    __tablename__ = "swaps"

    id = Column(Integer, unique=True, primary_key=True)
    swap_channel_discord_id = Column(Integer, nullable=True, default=None)
    period = Column(Enum(SwapPeriod), default=SwapPeriod.JOIN)

    join_button_message_id = Column(Integer, nullable=True, default=None)

    @staticmethod
    def list_swaps() -> list[Swap]:
        with Session(engine) as session:
            return session.query(Swap).all()

    @staticmethod
    def get_swap() -> Swap:
        with Session(engine) as session:
            try:
                return session.query(Swap).filter_by().limit(1).one()
            except NoResultFound as e:
                raise RuntimeError("No swap configured") from e

    @staticmethod
    def create_swap() -> Swap:
        with Session(engine) as session:
            try:
                swap = session.query(Swap).filter_by().limit(1).one()
                raise RuntimeError("Swap is already configured")
            except NoResultFound:
                pass
            swap = Swap()
            session.add(swap)
            session.commit()
        return swap

    @staticmethod
    def save_join_button_message_id(message_id: int) -> None:
        logger.info(f"Saving join button message id {message_id}")
        with Session(engine) as session:
            swap = Swap.get_swap()
            swap.join_button_message_id = message_id
            session.add(swap)
            session.commit()

    @staticmethod
    def get_join_button_message_id() -> int | None:
        try:
            swap = Swap.get_swap()
        except RuntimeError as e:
            if "No swap configured" in str(e):
                return None
            raise e
        assert (
            isinstance(swap.join_button_message_id, int)
            or swap.join_button_message_id is None
        )
        return swap.join_button_message_id

    @staticmethod
    def match_users() -> None:
        with Session(engine) as session:
            # find users where they have letters, and have no matched user
            users = session.query(SwapUser).filter_by(santa_id=None).all()
            logger.info(f"Found {len(users)} users with no santa")
            users = [u for u in users if u.letter is not None]
            logger.info(f"Found {len(users)} users with letters, with no santa")
            if len(users) < 2:
                raise RuntimeError(
                    f"Cannot match users without at least 2 unmatched users, currently have {len(users)} who have letters, but have no santa"
                )

            random.shuffle(users)

            logger.info(
                f"Shuffled users, random order: {[f'{u.user_id} {u.name}' for u in users]}"
            )

            # after shuffling the list, each person gets assigned the person in front of them as their giftee, and behind them as their santa
            for i, user in enumerate(users):
                user_before = users[i - 1]
                user_after = users[(i + 1) % len(users)]

                logger.info(
                    f"For user {user.user_id}, santa is {user_before.user_id}, giftee is {user_after.user_id}"
                )

                user.santa_id = user_before.user_id
                user.giftee_id = user_after.user_id
                session.add(user)

            session.commit()

    @staticmethod
    def unmatch_users() -> None:
        with Session(engine) as session:
            # set all users santa_id and giftee_id to None
            users = session.query(SwapUser).all()
            for user in users:
                logger.info(f"Unmatching user {user.user_id}")
                user.santa_id = None
                user.giftee_id = None
                session.add(user)
            session.commit()

    @staticmethod
    def set_swap_period(period: SwapPeriod) -> str | None:
        msg: str | None = None
        with Session(engine) as session:
            swap = Swap.get_swap()
            if period == SwapPeriod.SWAP:
                logger.info("Running db logic for SWAP period")
                if swap.swap_channel_discord_id is None:
                    raise RuntimeError(
                        "Cannot set swap period to swap without a swap channel, run '/filmswap-manage set-channel' command"
                    )
                try:
                    Swap.match_users()
                    msg = "Matched all users with their giftee/santas"
                except RuntimeError as e:
                    msg = f"Warning: couldnt match users -- {e}"
            elif period == SwapPeriod.JOIN:
                logger.info("Running db logic for JOIN period")
                # need to remove all santa_id/giftee_id's back to null, and remove gifts from users
                users = session.query(SwapUser).all()
                for user in users:
                    logger.info(f"Unmatching user {user.user_id}")
                    user.santa_id = None
                    user.giftee_id = None
                    user.gift = None
                    user.done_watching = False
                    session.add(user)

            swap.period = period
            session.add(swap)
            session.commit()

            logger.info(f"Done setting swap period to {period}")

        return msg

    @staticmethod
    def set_swap_channel(channel_id: int) -> None:
        with Session(engine) as session:
            swap = Swap.get_swap()
            swap.swap_channel_discord_id = channel_id
            session.add(swap)
            session.commit()

    @staticmethod
    def get_swap_period() -> SwapPeriod:
        swap = Swap.get_swap()
        assert isinstance(swap.period, SwapPeriod)
        return swap.period


class SwapUser(Base):
    __tablename__ = "swap_users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(32), nullable=False)

    # letter is what this user in this swap wants to receive from another user
    letter = Column(String(1900), nullable=True, default=None)
    # gift is what this user in this swap is giving to another user
    # this is NOT the users gift, this is what they've  set what they're giving to another user
    gift = Column(String(1900), nullable=True, default=None)

    # user can mark if they've finished watching, or a mod can do it for them if they post their thoughts
    done_watching = Column(Boolean, nullable=False, default=False)

    # santa is the user who is gifting to this user (i.e. santa)
    santa_id = Column(Integer, nullable=True, default=None)
    # giftee is the user who this user is gifting to (i.e. giftee)
    giftee_id = Column(Integer, nullable=True, default=None)


class Banned(Base):
    __tablename__ = "banned"

    user_id = Column(Integer, nullable=False, primary_key=True)

    @staticmethod
    def list_banned() -> list[Banned]:
        with Session(engine) as session:
            return session.query(Banned).all()


def ban_user(user_id: int) -> None:
    logger.info(f"Banning user {user_id}")
    with Session(engine) as session:
        # check if already banned
        if session.query(Banned).filter_by(user_id=user_id).count() > 0:
            logger.info(f"User {user_id} is already banned")
            raise RuntimeError("User is already banned")

        banned = Banned(user_id=user_id)
        session.add(banned)

        logger.info(f"Deleting user {user_id} from SwapUser")
        # delete from SwapUser if present
        session.query(SwapUser).filter_by(user_id=user_id).delete()

        session.commit()


def unban_user(user_id: int) -> None:
    with Session(engine) as session:
        if session.query(Banned).filter_by(user_id=user_id).count() == 0:
            logger.info(f"User {user_id} is not banned")
            raise RuntimeError("User is not banned")

        logger.info(f"Unbanning user {user_id}")
        session.query(Banned).filter_by(user_id=user_id).delete()
        session.commit()


def check_active_user(user_id: int) -> str | None:
    """
    returns an error message if the user is banned or not in the swap, otherwise None if active
    """
    with Session(engine) as session:
        banned = session.query(Banned).filter_by(user_id=user_id).count() > 0
        if banned:
            logger.info(f"User {user_id} is banned")
            return "You are banned from the swap, ask a mod to unban you"

        user = session.query(SwapUser).filter_by(user_id=user_id).count() > 0
        if user:
            return None
        else:
            logger.info(f"User {user_id} is not in the swap")
            return "You are not in the swap, click the 'join button' in the swap channel to join"


def set_gift_done(user_id: int) -> None:
    with Session(engine) as session:
        user = session.query(SwapUser).filter_by(user_id=user_id).one_or_none()
        if user is None:
            logger.info(f"User {user_id} is not in the swap")
            raise RuntimeError("User is not in the swap")

        if user.done_watching is True:
            logger.info(f"User {user_id} has already marked their gift done")
            raise RuntimeError(
                "Your gift has already been marked done! (this may have been done by a mod)"
            )

        user.done_watching = True
        session.add(user)
        session.commit()


def user_has_letter(user_id: int) -> bool:
    with Session(engine) as session:
        user = session.query(SwapUser).filter_by(user_id=user_id).one()
        return user.letter is not None


def join_swap(user_id: int, name: str) -> None:
    with Session(engine) as session:
        is_banned = session.query(Banned).filter_by(user_id=user_id).count() > 0

        if is_banned:
            logger.info(f"User {user_id} banned while trying to join swap")
            raise RuntimeError("You are banned from the swap, ask a mod to unban you")

        # check if user already in swap
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one_or_none()
        if swap_user is not None:
            logger.info(f"User {user_id} already in swap, updating name to {name}")
            swap_user.name = name
            raise RuntimeError(
                f"You are already in the swap, updated username to {name}"
            )
        else:
            logger.info(f"User {user_id} joined swap with name {name}")
            swap_user = SwapUser(user_id=user_id, name=name)
        session.add(swap_user)
        session.commit()


def leave_swap(user_id: int) -> None:
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one_or_none()
        if swap_user is None:
            logger.info(f"User {user_id} tried to leave swap but was not in swap")
            raise RuntimeError(
                "You are already not in the swap. To rejoin, click the 'join button' in the swap channel"
            )
        session.delete(swap_user)
        session.commit()


def set_letter(user_id: int, letter: str) -> None:
    """
    This is how a user sets their letter, to tell their santa what they want
    """
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        assert len(letter) <= 1900, "Letter too long, must be less than 1900 characters"
        logger.info(f"User {user_id} set their letter to {letter}")
        swap_user.letter = letter
        session.add(swap_user)
        session.commit()


def has_giftee(user_id: int) -> bool:
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        return swap_user.giftee_id is not None


def has_santa(user_id: int) -> bool:
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        return swap_user.santa_id is not None


def get_santa(user_id: int) -> SwapUser | None:
    with Session(engine) as session:
        return session.query(SwapUser).filter_by(santa_id=user_id).one_or_none()


def get_giftee(user_id: int) -> SwapUser | None:
    with Session(engine) as session:
        return session.query(SwapUser).filter_by(giftee_id=user_id).one_or_none()


def set_gift(user_id: int, gift: str) -> None:
    """
    This is how a user sets their gift, to tell their giftee what they're giving them
    """
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        assert len(gift) <= 1900, "Gift too long, must be less than 1900 characters"
        logger.info(f"User {user_id} set their gift for {swap_user.giftee_id}: {gift}")
        swap_user.gift = gift
        session.add(swap_user)
        session.commit()


def has_letter(user_id: int) -> bool:
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        return swap_user.letter is not None


def has_gift(user_id: int) -> bool:
    with Session(engine) as session:
        swap_user = session.query(SwapUser).filter_by(user_id=user_id).one()
        return swap_user.gift is not None


def review_my_letter_embed(user_id: int) -> discord.Embed:
    """
    Read your own letter, to review
    """

    with Session(engine) as session:
        swapuser = session.query(SwapUser).filter_by(user_id=user_id).one()
        if swapuser.letter is None:
            logger.info(
                f"User {user_id} tried to review their letter, but they haven't set it yet"
            )
            return discord.Embed(
                title="You haven't set your letter yet!",
                description="Use the `>letter` command to send your letter",
            )

    let = f"""Dear Santa,\n{swapuser.letter}\nLove, {swapuser.name}"""
    embed = discord.Embed(title="Your received a letter!", description=let)
    return embed


def review_my_gift_embed(user_id: int) -> discord.Embed:
    with Session(engine) as session:
        # read your own gift (what you sent as a recommendation), to review
        swapuser = session.query(SwapUser).filter_by(user_id=user_id).one()
        if swapuser.gift is None:
            logger.info(
                f"User {user_id} tried to review their gift, but they haven't set it yet"
            )
            return discord.Embed(
                title="You haven't set your gift yet!",
                description="Use the `>submit` command to set your gift",
            )

        given_to = session.query(SwapUser).filter_by(giftee_id=user_id).one_or_none()

        if given_to is None:
            logger.info(
                f"User {user_id} tried to review their gift, but they haven't been assigned a giftee yet"
            )
            return discord.Embed(
                title="You haven't been assigned a giftee yet!",
                description="You'll have to wait for the swap to start",
            )

        gift = f"""Dear {given_to.name}\n{swapuser.gift}\nLove, Santa"""
        embed = discord.Embed(title="Your received a gift!", description=gift)
        return embed


def receive_gift_embed(user_id: int) -> discord.Embed:
    """
    This is how a user receives their gift, to see what their santa recommended them
    """
    with Session(engine) as session:
        santa_user = session.query(SwapUser).filter_by(giftee_id=user_id).one_or_none()
        if santa_user is None:
            logger.info(
                f"User {user_id} tried to receive their gift, but they haven't been assigned a santa yet"
            )
            return discord.Embed(
                title="You don't have a santa yet!",
                description="If you joined late, you may get assigned one soon, or you'll have to wait for the next swap to start",
            )

        match Swap.get_swap():
            case SwapPeriod.JOIN:
                logger.info(
                    f"User {user_id} tried to receive their gift, but the swap hasn't started yet (currently in JOIN period)"
                )
                return discord.Embed(
                    title="The swap hasn't started yet!",
                    description="Once the 'swap' period has started, you can check again for your gift. If you haven't set your >letter yet, do so now!",
                )
            case SwapPeriod.SWAP:
                logger.info(
                    f"User {user_id} tried to receive their gift, but the swap hasn't started yet (currently in SWAP period)"
                )
                return discord.Embed(
                    title="The swap hasn't started yet!",
                    description="Once the 'watch' period starts, you can re-run this command to see your gift",
                )
            case _:
                pass

        if santa_user.gift is None:
            logger.info(
                f"User {user_id} tried to receive their gift, but their santa {santa_user.id} {santa_user.name} hasn't set it yet"
            )
            return discord.Embed(
                title="You haven't received a gift yet!",
                description="Please wait for your santa to send their gift. If the 'watch' period has already started, you can ask the mods to make sure your santa sent their gift",
            )

        my_swapuser = session.query(SwapUser).filter_by(user_id=user_id).one()

        gift = f"""Dear {my_swapuser.name}\n{santa_user.gift}\nLove, Santa"""

        embed = discord.Embed(title="Your received a gift!", description=gift)
        return embed


def read_giftee_letter(user_id: int) -> discord.Embed:
    with Session(engine) as session:
        # read your giftee's letter, this is how you find out what they want
        #
        # 'their santa_id is my user id', so we read their letter
        giftee_user = session.query(SwapUser).filter_by(santa_id=user_id).one_or_none()
        if giftee_user is None:
            logger.info(
                f"User {user_id} tried to read their giftee's letter, but they haven't been assigned a giftee yet"
            )
            return discord.Embed(
                title="You haven't been assigned a giftee yet!",
                description="You'll have to wait for the swap to start. If you think this is a mistake, ask a mod to check",
            )

        if giftee_user.letter is None:
            logger.info(
                f"User {user_id} tried to read their giftee's letter, but their giftee {giftee_user.id} {giftee_user.name} hasn't set it yet"
            )
            return discord.Embed(
                title="Your giftee hasn't set their letter yet!",
                description="Wait for your giftee to set their letter",
            )

        swap = Swap.get_swap()

        match swap.period:
            case SwapPeriod.JOIN:
                logger.info(
                    f"User {user_id} tried to read their giftee's letter, but the swap hasn't started yet (currently in JOIN period)"
                )
                return discord.Embed(
                    title="The swap hasn't started yet!",
                    description="Once the 'swap' period has started, you can check again for your giftee's letter",
                )
            case _:
                pass

        let = f"""Dear Santa,\n{giftee_user.letter}\nLove, {giftee_user.name}"""
        embed = discord.Embed(title="Your giftee sent a letter!", description=let)
        return embed


# sqlite database which stores data
engine = create_engine(
    f"sqlite:///{settings.SQLITEDB_PATH}",
    echo=settings.SQL_ECHO,
)

metadata.create_all(engine)
