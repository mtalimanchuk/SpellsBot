from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from spells_bot.bot.callback_schema import (
    BaseClassesCallback,
    ChatSettingsRemoveFilterCallback,
    ChatSettingsAddFilterCallback,
)
from spells_bot.bot.messages import buttons
from spells_bot.pathfinder_api.schemas import BotClassInfo, BotSpellInfo, BotBook


def try_inline_search(text: str = None, query: str = None):
    keyboard = [[buttons.try_inline_search_button(text, query)]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def start_main():
    return try_inline_search()


def help_main():
    return try_inline_search()


def menu_main(classes: [BotClassInfo]):
    keyboard = [[]]
    row_idx = 0
    max_columns_per_row = 3

    for c in classes:

        if len(keyboard[row_idx]) >= max_columns_per_row:
            row_idx += 1
            keyboard.append([])

        button = InlineKeyboardButton(text=c.name, callback_data=BaseClassesCallback(id=c.id).pack())
        keyboard[row_idx].append(button)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def menu_class(class_: BotClassInfo, show_tables_button: bool = True):
    keyboard = []

    if show_tables_button:
        keyboard.append([buttons.class_show_tables_button(class_.id)])

    spell_level_button_rows = buttons.class_spell_level_buttons(class_.id, class_.spellLevels)
    keyboard += spell_level_button_rows

    keyboard.append([buttons.class_main_menu_button()])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def menu_class_spell_level(
    class_: BotClassInfo,
    active_spell_level: int,
    show_tables_button: bool = True,
    active_page: int = 0,
    page_max: int = 0,
):
    keyboard = []

    if show_tables_button:
        keyboard.append([buttons.class_show_tables_button(class_.id)])

    if page_max > 0:
        spell_level_page_buttons = buttons.class_spell_level_page_buttons(
            class_.id, active_spell_level, active_page, page_max
        )
        keyboard.append(spell_level_page_buttons)

    spell_level_button_rows = buttons.class_spell_level_buttons(class_.id, class_.spellLevels, active_spell_level)
    keyboard += spell_level_button_rows

    keyboard.append([buttons.class_main_menu_button()])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def spellbook_empty():
    keyboard = [[buttons.spellbook_add_spell_button()]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def spellbook_main(spell: BotSpellInfo, index: int, index_max: int, extended: bool, tables: bool = False):
    keyboard = []
    if tables:
        keyboard.append([buttons.spell_show_tables_button(spell.id)])

    keyboard += [
        [buttons.spellbook_toggle_extended_button(extended, index)],
        buttons.spellbook_selector_buttons(extended, index, index_max),
        [buttons.spell_website_redirect_button(spell.alias)],
        [buttons.spellbook_delete_button(extended, index, spell.id)],
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def spellbook_main_prompt_delete_spell(spell: BotSpellInfo, index: int, index_max: int, extended: bool):
    keyboard = [
        [buttons.spellbook_toggle_extended_button(extended, index)],
        buttons.spellbook_selector_buttons(extended, index, index_max),
        [buttons.spell_website_redirect_button(spell.alias)],
        [buttons.spellbook_delete_confirm_button(extended, index, spell.id)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def spellbook_main_after_delete_spell(index: int, index_max: int, extended: bool):
    keyboard = [buttons.spellbook_selector_buttons(extended, index, index_max), [buttons.spellbook_add_spell_button()]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def extended_description_message(spell: BotSpellInfo, tables: bool = False):
    keyboard = [[buttons.spell_show_tables_button(spell.id)] if tables else []]

    keyboard += [
        [buttons.spell_website_redirect_button(spell.alias)],
        [buttons.spell_add_to_spellbook_button(spell.id)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def extended_description_message_saved_spell(spell: BotSpellInfo):
    keyboard = [[buttons.spell_website_redirect_button(spell.alias)]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def chat_settings(all_rulebooks: Sequence[BotBook], user_rulebooks: Sequence[int]):
    keyboard = []

    for book in all_rulebooks:
        if book.id in user_rulebooks:
            icon = "☑"
            callback_data = ChatSettingsRemoveFilterCallback(rulebook_id=book.id).pack()
        else:
            icon = "☐"
            callback_data = ChatSettingsAddFilterCallback(rulebook_id=book.id).pack()

        button = InlineKeyboardButton(text=f"{icon} {book.name}", callback_data=callback_data)
        keyboard.append([button])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
