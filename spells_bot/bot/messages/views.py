from typing import Sequence
from uuid import uuid4

from aiogram.types import (
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from spells_bot.bot.config import settings
from spells_bot.bot.messages import texts
from spells_bot.bot.messages import keyboards
from spells_bot.pathfinder_api.schemas import BotSpellInfo, BotClassInfo, BotBook, SchoolForList


def any_text_message(message_text: str):
    text = "Поиск работает в инлайн-режиме. Для справки перейдите в /help."
    keyboard = keyboards.try_inline_search(f'Искать "{message_text}"', message_text)
    return text, keyboard


def start_main():
    text = texts.start_main()
    keyboard = keyboards.start_main()
    return text, keyboard


def help_main(bot_name: str):
    text = texts.help_main(bot_name)
    keyboard = keyboards.help_main()
    return text, keyboard


def menu_main(classes: Sequence[BotClassInfo]):
    text = texts.menu_main()
    keyboard = keyboards.menu_main(classes)
    return text, keyboard


def menu_class(class_: BotClassInfo, show_tables_button: bool = True):
    text = texts.menu_class(class_)
    keyboard = keyboards.menu_class(class_, show_tables_button)
    return text, keyboard


def menu_class_spell_level(
    class_: BotClassInfo,
    spells: Sequence[BotSpellInfo],
    active_spell_level: int,
    page: int = 0,
    show_tables_button: bool = True,
):
    text_pages = texts.menu_class_spell_level(class_, spells, active_spell_level)

    keyboard = keyboards.menu_class_spell_level(
        class_, active_spell_level, show_tables_button, page, len(text_pages) - 1
    )
    return text_pages[page], keyboard


def extended_description_message(spell: BotSpellInfo):
    text, tables = texts.extended_description_message(spell)
    keyboard = keyboards.extended_description_message(spell, True if tables else False)
    return text, tables, keyboard


def spellbook_empty():
    text = texts.spellbook_empty()
    keyboard = keyboards.spellbook_empty()
    return text, keyboard


def spellbook_main(index: int, index_max: int, spell: BotSpellInfo, extended: bool = False):
    text, tables = texts.spellbook_main(spell, extended)
    keyboard = keyboards.spellbook_main(spell, index, index_max, extended, tables=True if tables else False)
    return text, keyboard


def spellbook_main_after_delete(index: int, index_max: int, extended: bool = False):
    text = texts.spellbook_main_after_delete_spell()
    keyboard = keyboards.spellbook_main_after_delete_spell(index, index_max, extended)
    return text, keyboard


def settings_main(all_rulebooks: Sequence[BotBook], user_rulebooks: Sequence[int], bot_name: str):
    text = texts.settings_main(bot_name)
    keyboard = keyboards.chat_settings(all_rulebooks, user_rulebooks)
    return text, keyboard


def _spell_url(spell: BotSpellInfo):
    prefix = settings.source.spell_info_url_prefix.rstrip("/")
    return f"{prefix}/{spell.alias}"


def _school_icon_url(school: SchoolForList):
    prefix = settings.storage.image_storage_url_root.rstrip("/")
    return f"{prefix}/schoolicons/{school.alias}.jpg"


def _settings_icon_url():
    return f"{settings.storage.settings_icon_url}"


def _warning_icon_url():
    return f"{settings.storage.warning_icon_url}"


def inline_results(
    query: str,
    spells: Sequence[BotSpellInfo],
    all_rulebooks: Sequence[BotBook],
    user_rulebooks: Sequence[int],
    chat_id: int,
    max_results: int = 20,
) -> [InlineQueryResultArticle]:
    articles = []

    if query and not spells:
        a = InlineQueryResultArticle(
            id=str(uuid4()),
            title=f"Ничего не найдено",
            description=f'по запросу "{query}"',
            input_message_content=InputTextMessageContent(
                message_text=texts.empty_inline_results_message(query), disable_web_page_preview=True
            ),
            reply_markup=keyboards.try_inline_search(),
            thumbnail_url=_warning_icon_url(),
        )
        articles.append(a)

    for s in spells[:max_results]:
        message_text, tables = texts.extended_description_message(s)
        a = InlineQueryResultArticle(
            id=str(uuid4()),
            title=s.name,
            description=texts.short_description_message(s, keep_links=False),
            input_message_content=InputTextMessageContent(message_text=message_text, disable_web_page_preview=True),
            reply_markup=keyboards.extended_description_message(s, tables=True if tables else False),
            thumbnail_url=_school_icon_url(s.school),
        )
        articles.append(a)

    settings_article = InlineQueryResultArticle(
        id=str(uuid4()),
        title="Настройки поиска",
        description=f"Фильтр по книгам ({len(user_rulebooks)}/{len(all_rulebooks)})",
        input_message_content=InputTextMessageContent(message_text=f"Настройте фильтр для чата {chat_id}"),
        reply_markup=keyboards.chat_settings(all_rulebooks, user_rulebooks),
        thumbnail_url=_settings_icon_url(),
    )
    articles.append(settings_article)

    return articles
