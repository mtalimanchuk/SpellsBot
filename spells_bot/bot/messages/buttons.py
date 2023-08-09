from typing import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton

from spells_bot.bot.callback_schema import (
    SpellbookReadCallback,
    EmptyCallback,
    SpellbookPromptDeleteCallback,
    SpellbookConfirmDeleteCallback,
    SpellbookCreateCallback,
    SpellTablesCallback,
    ClassesTableCallback,
    ClassesSpellsCallback,
    MenuClassCallback,
)
from spells_bot.config import settings

EMPTY_BUTTON_TEXT = "⠀"


def try_inline_search_button(text: str = None, query: str = None):
    return InlineKeyboardButton(text=text or "Поиск по названию", switch_inline_query_current_chat=query or "")


def empty_callback_button(text: str):
    return InlineKeyboardButton(text=text, callback_data=EmptyCallback().pack())


def spell_show_tables_button(spell_id: int):
    return InlineKeyboardButton(
        text="Показать таблицы",
        callback_data=SpellTablesCallback(spell_id=spell_id).pack(),
    )


def class_show_tables_button(class_id: int):
    return InlineKeyboardButton(
        text="Показать таблицы",
        callback_data=ClassesTableCallback(id=class_id).pack(),
    )


def spell_website_redirect_button(alias: str):
    return InlineKeyboardButton(text="🌐 На сайте", url=f"{settings.api.spell_info_url_prefix}/{alias}")


def spell_add_to_spellbook_button(spell_id: int):
    return InlineKeyboardButton(
        text="📖 Добавить в книгу заклинаний",
        callback_data=SpellbookCreateCallback(spell_id=spell_id).pack(),
    )


def spellbook_add_spell_button():
    return InlineKeyboardButton(text="Добавить новое", switch_inline_query_current_chat="")


def spellbook_toggle_extended_button(extended: bool, index: int):
    if extended:
        button = InlineKeyboardButton(
            text="Краткое описание", callback_data=SpellbookReadCallback(index=index, extended=False).pack()
        )
    else:
        button = InlineKeyboardButton(
            text="Полное описание", callback_data=SpellbookReadCallback(index=index, extended=True).pack()
        )

    return button


def arrow_selector_button(text: str, callback_data: CallbackData, is_active: bool = True):
    if is_active:
        button = InlineKeyboardButton(text=text, callback_data=callback_data.pack())
    else:
        button = InlineKeyboardButton(text=EMPTY_BUTTON_TEXT, callback_data=EmptyCallback().pack())

    return button


def index_view_selector_button(text: str):
    return empty_callback_button(text)


def spellbook_left_arrow_button(index: int, extended: bool, is_active: bool = True):
    return arrow_selector_button("<", SpellbookReadCallback(index=index - 1, extended=extended), is_active)


def spellbook_right_arrow_button(index: int, extended: bool, is_active: bool = True):
    return arrow_selector_button(">", SpellbookReadCallback(index=index + 1, extended=extended), is_active)


def spellbook_selector_buttons(extended: bool, index: int, index_max: int):
    row = [
        spellbook_left_arrow_button(index, extended, is_active=index > 0),
        index_view_selector_button(f"{index + 1}/{index_max}"),
        spellbook_right_arrow_button(index, extended, is_active=index < index_max - 1),
    ]
    return row


def class_left_arrow_button(class_id: int, spell_level: int, page: int, is_active: bool = True):
    return arrow_selector_button(
        "<", ClassesSpellsCallback(id=class_id, spell_level=spell_level, page=page - 1), is_active
    )


def class_right_arrow_button(class_id: int, spell_level: int, page: int, is_active: bool = True):
    return arrow_selector_button(
        ">", ClassesSpellsCallback(id=class_id, spell_level=spell_level, page=page + 1), is_active
    )


def class_spell_level_page_buttons(class_id: int, spell_level: int, page: int, page_max: int):
    row = [
        class_left_arrow_button(class_id, spell_level, page, is_active=page > 0),
        index_view_selector_button(f"Страница {page + 1}/{page_max + 1}"),
        class_right_arrow_button(class_id, spell_level, page, is_active=page < page_max),
    ]
    return row


def class_spell_level_buttons(class_id: int, spell_levels: Sequence[int], active_spell_level: int = None):
    spell_level_button_rows = [[]]
    spell_level_row_idx = 0
    max_columns_per_row = 5

    for level in spell_levels:

        if len(spell_level_button_rows[spell_level_row_idx]) >= max_columns_per_row:
            spell_level_row_idx += 1
            spell_level_button_rows.append([])

        if active_spell_level is not None and level == active_spell_level:
            text = "🔘"
            callback_data = EmptyCallback().pack()
        else:
            text = str(level)
            callback_data = ClassesSpellsCallback(id=class_id, spell_level=level).pack()

        button = InlineKeyboardButton(text=text, callback_data=callback_data)
        spell_level_button_rows[spell_level_row_idx].append(button)

    return spell_level_button_rows


def class_main_menu_button():
    return InlineKeyboardButton(text="Назад в меню", callback_data=MenuClassCallback().pack())


def spellbook_delete_button(extended: bool, index: int, spell_id: int):
    return InlineKeyboardButton(
        text="🗑️ Удалить",
        callback_data=SpellbookPromptDeleteCallback(index=index, spell_id=spell_id, extended=extended).pack(),
    )


def spellbook_delete_confirm_button(extended: bool, index: int, spell_id: int):
    return InlineKeyboardButton(
        text="⚠ Подтвердить удаление",
        callback_data=SpellbookConfirmDeleteCallback(index=index, spell_id=spell_id, extended=extended).pack(),
    )
