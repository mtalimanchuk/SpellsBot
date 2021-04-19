#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
import json
import logging
from pathlib import Path
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
    CORE_CLASSES = {
        "Адепт": "adept",
        "Бард": "bard",
        "Волшебник": "wizard",
        "Друид": "druid",
        "Жрец": "priest",
        "Паладин": "paladin",
        "Следопыт": "ranger",
        "Чародей": "sorcerer",
    }

    def __init__(self, spells_csv: str, classes_csv: str, data_dir: str) -> None:
        self.spells_df = self._load_df(spells_csv)
        self.classes_df = self._load_df(classes_csv)
        self.data_dir = Path(data_dir)

    @staticmethod
    def _load_df(csv_path: str) -> pd.DataFrame:
        df = pd.read_csv(csv_path)
        df.fillna("", inplace=True)

        return df

    def _get_table_caption(self, spell_id: str) -> str:
        return dict(
            self.spells_df.loc[
                self.spells_df["spell_id"] == spell_id, ["name", "Круг"]
            ].iloc[0]
        )

    def __call__(self, query: str):
        results_df = self.spells_df[
            self.spells_df["name"].str.lower().str.contains(query.lower())
        ]

        for idx, row in results_df.iterrows():
            yield dict(row)

    def class_info(self, class_id: str):
        c_row = self.classes_df.loc[self.classes_df["class_id"] == class_id]
        c = c_row.to_dict("records")[0]
        return c

    def iter_spell_tables(self, spell_id: str):
        spell_tables_dir = self.data_dir / "tables" / spell_id

        for p in spell_tables_dir.glob("*.png"):
            caption = self._get_table_caption(spell_id)
            yield p, caption

    def iter_levels(self, player_class: str):
        levels = (
            self.spells_df["Круг"]
            .str.extract(rf"{player_class} (\d)", expand=False)
            .dropna()
            .astype(int)
        )
        for lvl in set(levels):
            yield str(lvl)

    def iter_classes(self):
        for idx, c in self.classes_df.iterrows():
            yield dict(c)

    def iter_class_info_tables(self, class_id: str):
        class_info_dir = self.data_dir / "classinfo" / class_id

        for p in class_info_dir.glob("*.png"):
            caption = self.class_info(class_id)
            yield p, caption

    def by_level(self, class_and_level: str):
        results_df = self.spells_df.loc[
            self.spells_df["Круг"].str.contains(class_and_level),
            ["name", "sup", "short_desc", "school"],
        ]

        for school, row in results_df.groupby("school"):
            yield school, row.to_dict("records")


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
        classes_csv: str,
        data_dir: str,
        bot_url_root: str,
        spell_url_root: str,
    ) -> None:
        self.spell_search = SpellSearch(spells_csv, classes_csv, data_dir)
        self.bot_url_root = bot_url_root.rstrip("/")
        self.spell_url_root = spell_url_root.rstrip("/")

    def _spell_url(self, spell_id: str):
        return f"{self.spell_url_root}/{spell_id}"

    def _bot_url(self, payload: str = None):
        url = f"{self.bot_url_root}"
        if payload:
            f"{url}?start={payload}"

        return url

    @staticmethod
    def decode_callback(data: str):
        cmd, payload = data.split(":", maxsplit=1)
        return cmd, payload

    @staticmethod
    def encode_callback(cmd: str, payload: str = ""):
        return f"{cmd}:{payload}"

    def greet(self):
        text = (
            "Начните вводить:\n\n<code>@SpellsBot название заклинания</code>\n\n"
            "в любом чате и выберите нужный результат. Этот результат отправится в текущий чат.\n\n"
            "Для поиска по классам и кругам используйте /menu"
        )
        kb_markup = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(
                "Попробуйте поиск в этом чате", switch_inline_query_current_chat=""
            )
        )

        return dict(text=text, reply_markup=kb_markup, parse_mode=ParseMode.HTML)

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

            description = f"{spell['Круг']}\n{spell['short_desc']}"

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
                        callback_data=self.encode_callback("TABLE", spell["spell_id"]),
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

    def send_spell_tables(self, chat_id: str, spell_id: str):
        media_group = []
        for p, cap in self.spell_search.iter_spell_tables(spell_id):
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

    def menu(self):
        text = "📖 <b>МЕНЮ</b> 🔮\n\nВыберите класс"
        buttons = [
            InlineKeyboardButton(
                c["name"], callback_data=self.encode_callback("CLASS", c["class_id"])
            )
            for c in self.spell_search.iter_classes()
        ]
        button_rows = [buttons[i : i + 3] for i in range(0, len(buttons) + 1, 3)]

        return dict(
            text=text,
            reply_markup=InlineKeyboardMarkup(button_rows),
            parse_mode=ParseMode.HTML,
        )

    def menu_class(self, class_id: str, tables_button=True):
        c = self.spell_search.class_info(class_id)

        c_info = "\n".join(
            f"<b>{k}</b>: {c[k]}" for k in ["КЗ", "Пункты навыков за уровень"]
        )
        text = f"<b>{c['name']}</b>\n\n{c_info}"

        buttons = []
        for lvl in self.spell_search.iter_levels(c["name"]):
            b = InlineKeyboardButton(
                lvl, callback_data=self.encode_callback("LEVEL", f"{c['name']} {lvl}")
            )
            buttons.append(b)

        class_info_button = InlineKeyboardButton(
            " О классе", callback_data=self.encode_callback("CLASSINFO", class_id)
        )
        home_button = InlineKeyboardButton(
            "🔮 Назад в меню", callback_data=self.encode_callback("HOME")
        )

        button_rows = [buttons[i : i + 5] for i in range(0, len(buttons) + 1, 5)]
        if tables_button:
            button_rows.insert(0, [class_info_button])
        button_rows.append([home_button])

        return dict(
            text=text,
            reply_markup=InlineKeyboardMarkup(button_rows),
            parse_mode=ParseMode.HTML,
        )

    def class_info_delimiter(self, class_id: str):
        c = self.spell_search.class_info(class_id)

        return dict(
            text=f"📜 <b>{c['name'].upper()}</b> 📜",
            parse_mode=ParseMode.HTML,
        )

    def send_class_info_tables(self, class_id: str):
        media_group = []
        for p, cap in self.spell_search.iter_class_info_tables(class_id):
            caption = f"<b>{cap['name'].upper()}</b> <i>таблица {int(p.stem) + 1}</i>"
            m = InputMediaPhoto(
                p.open("rb"),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            media_group.append(m)

        return dict(media=media_group)

    def menu_level(self, class_and_level: str):
        text_parts = [f"<b>{class_and_level} круг</b>"]

        for school, spells in self.spell_search.by_level(class_and_level):
            text_parts.append(f"\n<b>{school}</b>")
            for s in spells:
                text_parts.append(
                    f"<u>{s['name']}</u> <code>{s['sup']}</code>: <i>{s['short_desc']}</i>"
                )

        text = "\n".join(text_parts)

        class_name, level = class_and_level.split(" ", maxsplit=1)
        buttons = []
        for lvl in self.spell_search.iter_levels(class_name):
            b_text = lvl
            b_callback_data = self.encode_callback("LEVEL", f"{class_name} {lvl}")
            if lvl == level:
                b_text = "🔘"
                b_callback_data = "PASS"
            b = InlineKeyboardButton(b_text, callback_data=b_callback_data)
            buttons.append(b)

        button_rows = [buttons[i : i + 5] for i in range(0, len(buttons) + 1, 5)]
        button_rows.append(
            [
                InlineKeyboardButton(
                    "🔮 Назад в меню", callback_data=self.encode_callback("HOME")
                )
            ]
        )

        return dict(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(button_rows),
        )


"""
BOT HANDLERS

"""


def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    try:
        user_id = update.effective_user.id
        spell_id = context.args[0]

        context.bot.send_media_group(**responder.send_spell_tables(user_id, spell_id))
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


def menu(update: Update, context: CallbackContext):
    """Send main menu message"""
    update.message.reply_text(**responder.menu())


def tables_callback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cmd, spell_id = Responder.decode_callback(update.callback_query.data)

    try:
        context.bot.send_media_group(**responder.send_spell_tables(user_id, spell_id))
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


def home_callback(update: Update, context: CallbackContext):
    cmd, class_name = Responder.decode_callback(update.callback_query.data)
    update.effective_message.edit_text(**responder.menu())
    update.callback_query.answer("")


def class_callback(update: Update, context: CallbackContext):
    cmd, class_id = Responder.decode_callback(update.callback_query.data)
    update.effective_message.edit_text(**responder.menu_class(class_id))
    update.callback_query.answer("")


def class_info_callback(update: Update, context: CallbackContext):
    cmd, class_id = Responder.decode_callback(update.callback_query.data)
    update.effective_message.reply_text(**responder.class_info_delimiter(class_id))
    update.effective_message.reply_media_group(
        **responder.send_class_info_tables(class_id)
    )
    update.effective_message.delete()
    update.effective_message.reply_text(
        **responder.menu_class(class_id, tables_button=False)
    )
    update.callback_query.answer("")


def level_callback(update: Update, context: CallbackContext):
    cmd, class_and_level = Responder.decode_callback(update.callback_query.data)
    update.effective_message.edit_text(**responder.menu_level(class_and_level))
    update.callback_query.answer("")


def pass_callback(update: Update, context: CallbackContext):
    update.callback_query.answer("")


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
    classes_csv = env.path("CLASSES_CSV")
    data_root_dir = env.path("DATA_ROOT_DIR")
    spell_url_root = env.str("SPELL_URL_ROOT")

    updater = Updater(bot_token)
    responder = Responder(
        spells_csv, classes_csv, data_root_dir, updater.bot.link, spell_url_root
    )

    h = updater.dispatcher.add_handler
    eh = updater.dispatcher.add_error_handler

    h(CommandHandler("start", start))
    h(CommandHandler("help", help))
    h(CommandHandler("menu", menu))
    h(InlineQueryHandler(inline_query))
    h(CallbackQueryHandler(tables_callback, pattern=r"TABLE:.*"))
    h(CallbackQueryHandler(home_callback, pattern=r"^HOME:.*"))
    h(CallbackQueryHandler(class_callback, pattern=r"CLASS:.*"))
    h(CallbackQueryHandler(class_info_callback, pattern=r"CLASSINFO:.*"))
    h(CallbackQueryHandler(level_callback, pattern=r"LEVEL:.*"))
    h(CallbackQueryHandler(pass_callback, pattern=r"^PASS$"))
    eh(error)

    updater.start_polling()
    logger.info("BOT DEPLOYED. Ctrl+C to terminate")

    updater.idle()
