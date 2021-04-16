#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
import json
import logging
from pathlib import Path
from typing import Generator
from uuid import uuid4

from environs import Env
import pandas as pd
from telegram import (
    Update,
    ParseMode,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InputMediaPhoto,
)
from telegram.ext import (
    CallbackContext,
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackQueryHandler,
)


logger = logging.getLogger("SpellsBot")
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.addHandler(handler)
logger.setLevel("INFO")


"""
UTILITIES
"""


class SpellSearch:
    def __init__(self, spells_csv) -> None:
        self.df = self._load_df(spells_csv)

    @staticmethod
    def _load_df(csv_path: str) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        df.fillna("", inplace=True)

        return df

    def __call__(self, query: str) -> Generator:
        results_df = self.df[self.df["name"].str.lower().str.contains(query.lower())]

        for idx, row in results_df.iterrows():
            yield dict(row)

    def get_table_caption(self, spell_id: str) -> str:
        return dict(
            self.df.loc[self.df["spell_id"] == spell_id, ["name", "Круг"]].iloc[0]
        )


class Responder:
    """

    Public methods should return a dict of kwargs for a specific ptb response method, e.g.:
    ```
    def hello(self, name: str):
        text = f"*Hello, {name}!*"
        return dict(text=text, parse_mode=ParseMode.MARKDOWN)
    ```

    The returned value should be unpacked and sent to the ptb method, e.g.:
    ```
    def start(update: Update, context: CallbackContext):
        update.message.reply_text(**responder.hello())
    ```
    """

    def __init__(
        self,
        spells_csv: str,
        images_root_dir: str,
        bot_url_root: str,
        spell_url_root: str,
    ) -> None:
        self.spell_search = SpellSearch(spells_csv)
        self.images_root_dir = Path(images_root_dir)
        self.bot_url_root = bot_url_root.rstrip("/")
        self.spell_url_root = spell_url_root.rstrip("/")

    def _spell_url(self, spell_id: str):
        return f"{self.spell_url_root}/{spell_id}"

    def _bot_url(self, payload: str = None):
        url = f"{self.bot_url_root}"
        if payload:
            f"{url}?start={payload}"

        return url

    def greet(self):
        text = (
            "Начните вводить *@SpellsBot название заклинания* в любом чате "
            "и выберите нужный результат. Этот результат отправится в текущий чат."
        )
        kb_markup = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(
                "Попробуйте поиск в этом чате", switch_inline_query_current_chat=""
            )
        )

        return dict(text=text, reply_markup=kb_markup, parse_mode=ParseMode.MARKDOWN)

    def help(self):
        text = (
            "Начните вводить *@SpellsBot название заклинания* в любом чате "
            "и выберите нужный результат. Этот результат отправится в текущий чат."
        )

        return dict(text=text, parse_mode=ParseMode.MARKDOWN)

    def search(self, query: str):
        articles = []
        for spell in self.spell_search(query):

            title = spell["name"]
            if spell["sup"]:
                title += f" ({spell['sup']})"

            description = f"{spell['short_desc']}"

            text_parts = [f"*{spell['title'].upper()}*", f"{spell['school']}\n"]
            for key in [
                # 'Источник',
                "Круг",
                "Время сотворения",
                "Компоненты",
                "Дистанция",
                "Эффект",
                "Длительность",
                "Испытание",
                "Устойчивость к магии",
                "Цель",
                "Область",
            ]:
                if spell[key]:
                    text_parts.append(f"*{key}*: {spell[key]}")
            text_parts.append(f"\n{spell['text']}")
            text = "\n".join(text_parts)

            buttons = []
            buttons.append(
                InlineKeyboardButton(
                    "🌐 На сайте",
                    url=self._spell_url(spell["spell_id"]),
                )
            )
            try:
                n_tables = len(json.loads(spell["tables"]))
                buttons.append(
                    InlineKeyboardButton(
                        f"📜 Показать таблицы ({n_tables})",
                        callback_data=spell["spell_id"],
                    )
                )
            except json.decoder.JSONDecodeError:
                pass

            a = InlineQueryResultArticle(
                id=uuid4(),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    text, parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=InlineKeyboardMarkup.from_column(buttons),
            )
            articles.append(a)

        return dict(results=articles)

    def send_tables(self, chat_id: str, spell_id: str):
        tables_dir = self.images_root_dir / spell_id

        media_group = []
        for p in tables_dir.glob("*.png"):
            cap = self.spell_search.get_table_caption(spell_id)

            caption = (
                f"<b>{cap['name'].upper()}</b> <i>таблица {int(p.stem) + 1}</i>\n"
                f"{cap['Круг']}"
            )
            m = InputMediaPhoto(
                p.open("rb"),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            media_group.append(m)

        return dict(chat_id=chat_id, media=media_group)

    def redirect_button(self, spell_id: str):
        buttons = []
        buttons.append(
            InlineKeyboardButton(
                "🌐 На сайте",
                url=self._spell_url(spell_id),
            )
        )
        buttons.append(
            InlineKeyboardButton(
                "Перейти в чат с ботом",
                url=self._bot_url(spell_id),
            )
        )

        return dict(reply_markup=InlineKeyboardMarkup.from_column(buttons))


"""
BOT HANDLERS

"""


def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    try:
        user_id = update.effective_user.id
        spell_id = context.args[0]

        context.bot.send_media_group(**responder.send_tables(user_id, spell_id))
    except IndexError:
        update.message.reply_text(**responder.greet())


def help(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text(**responder.help())


def inline_query(update: Update, context: CallbackContext):
    """Handle the inline query."""
    user = update.inline_query.from_user["username"]
    query = update.inline_query.query.lower().strip()

    if not query:
        return

    logger.info(f'User @{user} searched "{query}"')

    update.inline_query.answer(**responder.search(query))


def tables_callback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    spell_id = update.callback_query.data

    try:
        context.bot.send_media_group(**responder.send_tables(user_id, spell_id))
        update.callback_query.answer("")
    except Exception as e:
        logger.info(
            f"Redirecting to bot chat on 'show tables' click because {type(e)}: {e}"
        )

        update.callback_query.answer(
            "Перейдите в чат с ботом, чтобы посмотреть таблицы", show_alert=True
        )
        update.callback_query.edit_message_reply_markup(
            **responder.redirect_button(spell_id)
        )


def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f"Update {update} caused error {context.error}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-e", "--env", type=Path, required=True)
    options = parser.parse_args()

    env = Env()
    env.read_env(options.env, override=True)

    bot_token = env.str("BOT_TOKEN")
    spells_csv = env.path("SPELLS_CSV")
    images_root_dir = env.path("IMAGES_ROOT_DIR")
    spell_url_root = env.str("SPELL_URL_ROOT")

    updater = Updater(bot_token)
    responder = Responder(spells_csv, images_root_dir, updater.bot.link, spell_url_root)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_handler(CallbackQueryHandler(tables_callback))
    dp.add_error_handler(error)

    updater.start_polling()
    logger.info("BOT DEPLOYED. Ctrl+C to terminate")

    updater.idle()
