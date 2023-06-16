# filmswap

bot to anonymously swap films with other users to watch

## Installation

Run on `python 3.11.3`

Create an `.env` file with values like:

```
SQLITEDB_PATH="filmswap.db"
SQL_ECHO=0
GUILD_ID=9243234234
ALLOWED_ROLES='["filmwap-mod", "Chat Moderators"]'
```

```
git clone https://github.com/seanbreckenridge/filmswap
cd filmswap
pyenv install 3.11.3
pipenv --python ~/.pyenv/versions/3.11.3/bin/python install
pipenv install
pipenv run bot
```

This runs a swap as a singleton, adding multiple swaps per server was originally supported but it makes the commands a bit more complicated, and I don't think its worth the complication.
To create a swap, run `/create`, then `/set-channel`, then `/send-join-message` to send a message to the channel to join the swap.

Once users have joined then can set their `>letter`s telling the bot what they want to watch

Then, `/set-period SWAP` will start the swap period, matching users up with santa/giftee pairs, users can then use `/read` and `/submit` to read and submit their films, and `>write-giftee`/`>write-santa` to anonymously communicate with their giftee/santas

If people join late, you can use admin `match-users` command to match them up with other users who joined late (Requires at least 2 late joiners)

Then, once all the films are submitted, you can use `/set-period WATCH` to start the watch period, where users can watch the films they were given, and use `/done-watching` to mark them as watched (or an admin can use `/set-user-done-watching` to do so)

## TODO

- add `reveal` command, which is used to create a report of who was whose santa/giftee
