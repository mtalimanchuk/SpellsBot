import json
from typing import Dict, Union
from uuid import uuid4

from telegram import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ParseMode,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InputMediaPhoto,
)
from telegram.constants import MAX_MESSAGE_LENGTH, MAX_INLINE_QUERY_RESULTS

from spells_bot.config import BotSettings
from spells_bot.search import SpellSearch


school_translation = {
    "преграждения": "abjuration",
    "воплощения": "conjuration",
    "прорицания": "divination",
    "очарования": "enchantment",
    "разрушения": "evocation",
    "иллюзии": "illusion",
    "некромантии": "necromancy",
    "превращения": "transmutation",
    "универсализма": "universalist",
}


def _school_ru2en(full_ru_name: str) -> str:
    ru_name = full_ru_name.split(" ")[1].lower()
    return school_translation[ru_name]


def _book_alias_to_readable_name(book_alias: str) -> str:
    words = []
    current_word = ""

    for char in book_alias:
        if char.isupper():
            words.append(current_word)
            current_word = ""
        current_word += char

    if current_word:
        words.append(current_word)

    return " ".join(w.capitalize() for w in words)


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
        settings: BotSettings,
        bot_url_root: str,
    ) -> None:
        self._settings = settings

        self.search = SpellSearch(
            settings.db, settings.storage, settings.source, settings.hcti
        )
        self.bot_url_root = bot_url_root.rstrip("/")

    def _spell_url(self, spell_id: str):
        prefix = self._settings.source.spell_info_url_prefix.rstrip("/")
        return f"{prefix}/{spell_id}"

    def _school_icon_url(self, school: str):
        prefix = self._settings.storage.image_storage_url_root.rstrip("/")
        return f"{prefix}/schoolicons/{school}.jpg"

    def _settings_icon_url(self):
        return f"{self._settings.storage.settings_icon_url}"

    def _bot_url(self, payload: str = None):
        url = f"{self.bot_url_root}"
        if payload:
            f"{url}?start={payload}"

        return url

    @staticmethod
    def decode_callback(data: str, n_args: int = -1):
        cmd, *payload = data.split(":", maxsplit=n_args)
        return cmd, *payload

    @staticmethod
    def encode_callback(cmd: Union[int, str], *payload: Union[int, str]):
        return ":".join(str(i) for i in [cmd, *payload])

    def _book_filter_markup(self, book_filter: Dict[str, bool]):

        book_filter_buttons = []
        for book, value in book_filter.items():
            icon = "☑" if value else "☐"
            book_readable_name = _book_alias_to_readable_name(book)
            btn = InlineKeyboardButton(
                f"{book_readable_name} {icon}",
                callback_data=self.encode_callback("SETTINGS", book),
            )
            book_filter_buttons.append(btn)

        return InlineKeyboardMarkup.from_column(book_filter_buttons)

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

    def inline_search(self, query: str, chat_id: int):
        articles = []
        for spell in self.search.short_info(
            query, chat_id, top_n=MAX_INLINE_QUERY_RESULTS - 1
        ):
            spell_ext = self.search.extended_info(spell.alias)

            title = spell.name
            if spell.short_description_components:
                title += f" ({spell.short_description_components})"

            class_restrictions = ", ".join(f"{c.name} {c.level}" for c in spell.classes)
            school = ", ".join(s.name for s in spell.schools)
            description = f"{class_restrictions}\n{spell.short_description}"

            text_parts = [
                f"<b>{spell_ext.full_name.upper()}</b>",
                f"{school}\n",
                "\n".join(f"<b>{k}</b>: {v}" for k, v in spell_ext.variables.items()),
                f"\n{spell_ext.text}",
            ]
            text = "\n".join(text_parts)

            if len(text) >= MAX_MESSAGE_LENGTH:
                text_ending = " <i>... продолжение по ссылке</i>"
                cutoff = MAX_MESSAGE_LENGTH - len(text_ending)
                text = text[:cutoff] + text_ending

            buttons = []
            buttons.append(
                InlineKeyboardButton(
                    "🌐 На сайте",
                    url=self._spell_url(spell.alias),
                )
            )
            try:
                n_tables = len(spell_ext.tables)
                if n_tables > 0:
                    buttons.append(
                        InlineKeyboardButton(
                            f"📜 Показать таблицы ({n_tables})",
                            callback_data=self.encode_callback("TABLE", spell.alias),
                        )
                    )
            except json.decoder.JSONDecodeError:
                pass

            en_school_name = _school_ru2en(spell_ext.school)
            a = InlineQueryResultArticle(
                id=str(uuid4()),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    text, parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup.from_column(buttons),
                thumb_url=self._school_icon_url(en_school_name),
            )
            articles.append(a)

        chat_settings = self.search.get_chat_settings(chat_id)
        current_book_filter = [
            _book_alias_to_readable_name(k)
            for k, v in chat_settings.book_filter.items()
            if v
        ]
        current_book_filter = ", ".join(current_book_filter)
        settings_article_description = f"Фильтр по книгам: {current_book_filter}"

        settings_article = InlineQueryResultArticle(
            id=str(uuid4()),
            title="Настройки поиска",
            description=settings_article_description,
            input_message_content=InputTextMessageContent(
                f"Настройте фильтр для чата {chat_id}"
            ),
            reply_markup=self._book_filter_markup(chat_settings.book_filter),
            thumb_url=self._settings_icon_url(),
        )
        articles.append(settings_article)
        return dict(results=articles)

    # def send_search_settings(self, chat_id: int):
    #     return dict(
    #         chat_id=chat_id,
    #         text=f"Настройте фильтр для чата {chat_id}",
    #         reply_markup=self._book_filter_markup(chat_id),
    #     )

    def update_search_settings(self, chat_id: int, book: str):
        chat_settings = self.search.update_chat_settings(chat_id, book)
        return dict(reply_markup=self._book_filter_markup(chat_settings.book_filter))

    def send_spell_tables(self, chat_id: str, spell_alias: str):
        media_group = []
        spell_short, spell_ext = self.search.full_info(spell_alias)
        for t in spell_ext.tables:
            class_restrictions = ", ".join(
                f"{c.name} {c.level}" for c in spell_short.classes
            )
            caption = (
                f"<b>{spell_ext.full_name.upper()}</b> "
                f"<i>таблица {int(t.path.stem) + 1}</i>\n"
                f"{class_restrictions}"
            )
            m = InputMediaPhoto(
                t.path.open("rb"),
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

    def menu(self, chat_id: int):
        text = "📖 <b>МЕНЮ</b> 🔮\n\nВыберите класс"
        buttons = [
            InlineKeyboardButton(
                c.name, callback_data=self.encode_callback("CLASS", c.id)
            )
            for c in self.search.iter_classes(chat_id)
        ]
        button_rows = [buttons[i : i + 3] for i in range(0, len(buttons) + 1, 3)]

        return dict(
            text=text,
            reply_markup=InlineKeyboardMarkup(button_rows),
            parse_mode=ParseMode.HTML,
        )

    def menu_class(self, class_id: str, tables_button: bool = True):
        c = self.search.class_info(int(class_id))

        text = f"<b>{c.name}</b>\n\n<i>{c.short_description}</i>"
        buttons = []
        for lvl in self.search.iter_levels(int(class_id)):
            b = InlineKeyboardButton(
                lvl, callback_data=self.encode_callback("LEVEL", c.id, lvl, 0)
            )
            buttons.append(b)

        class_info_button = InlineKeyboardButton(
            " О классе", callback_data=self.encode_callback("CLASSINFO", class_id)
        )
        home_button = InlineKeyboardButton(
            "🔮 Назад в меню", callback_data=self.encode_callback("HOME")
        )

        button_rows = [buttons[i : i + 5] for i in range(0, len(buttons) + 1, 5)]
        has_tables = len(list(self.search.iter_class_info_tables(int(class_id)))) > 0
        if tables_button and has_tables:
            button_rows.insert(0, [class_info_button])

        button_rows.append([home_button])

        return dict(
            text=text,
            reply_markup=InlineKeyboardMarkup(button_rows),
            parse_mode=ParseMode.HTML,
        )

    def class_info_delimiter(self, class_id: str):
        c = self.search.class_info(int(class_id))

        return dict(
            text=f"📜 <b>{c.name.upper()}</b> 📜",
            parse_mode=ParseMode.HTML,
        )

    def send_class_info_tables(self, class_id: str):
        media_group = []
        for p, class_info in self.search.iter_class_info_tables(int(class_id)):
            caption = (
                f"<b>{class_info.name.upper()}</b> <i>таблица {int(p.stem) + 1}</i>"
            )
            m = InputMediaPhoto(
                p.open("rb"),
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            media_group.append(m)

        return dict(media=media_group)

    def menu_level(self, class_id: str, level: str, chat_id: str, page: str = 0):
        class_id, level, page, chat_id = (
            int(class_id),
            int(level),
            int(page),
            int(chat_id),
        )

        class_info = self.search.class_info(class_id)

        text_parts = [f"<b>{class_info.name} {level} круг</b>"]
        n_pages, spells = self.search.paginate_short_info_by_level(
            class_id, level, chat_id, page
        )
        for s in spells:
            text_parts.append(f"<u>{s.name}</u>: <i>{s.short_description}</i>")
        text = "\n".join(text_parts)

        buttons = []

        pagination_buttons = []
        if n_pages >= 1:
            if page >= 1:
                b = InlineKeyboardButton(
                    f"<< Страница {page}",
                    callback_data=self.encode_callback(
                        "LEVEL", class_id, level, page - 1
                    ),
                )
                pagination_buttons.append(b)
            if page < n_pages - 1:
                b = InlineKeyboardButton(
                    f"Страница {page + 2} >>",
                    callback_data=self.encode_callback(
                        "LEVEL", class_id, level, page + 1
                    ),
                )
                pagination_buttons.append(b)

        for lvl in self.search.iter_levels(class_id):
            b_text = lvl
            b_callback_data = self.encode_callback("LEVEL", class_id, lvl, 0)
            if lvl == level:
                b_text = "🔘"
                b_callback_data = "PASS"
            b = InlineKeyboardButton(b_text, callback_data=b_callback_data)
            buttons.append(b)

        button_rows = [buttons[i : i + 5] for i in range(0, len(buttons) + 1, 5)]

        if pagination_buttons:
            button_rows.insert(0, pagination_buttons)

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
