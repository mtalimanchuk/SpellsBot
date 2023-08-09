from aiogram.filters.callback_data import CallbackData


class MenuClassCallback(CallbackData, prefix="MENU_CLS"):
    """"""


class BaseClassesCallback(CallbackData, prefix="CLS"):
    id: int


class ClassesTableCallback(BaseClassesCallback, prefix="CLS_TABLE"):
    """"""


class ClassesSpellsCallback(BaseClassesCallback, prefix="CLS_SPELL"):
    """"""
    spell_level: int
    page: int | None = 0


class SpellTablesCallback(CallbackData, prefix="SPELL_TABLE"):
    spell_id: int


class SpellbookReadCallback(CallbackData, prefix="BOOK_R"):
    index: int
    spell_id: int | None = None
    extended: bool = False


class SpellbookCreateCallback(CallbackData, prefix="BOOK_C"):
    spell_id: int | None = None


class SpellbookPromptDeleteCallback(SpellbookReadCallback, prefix="BOOK_TRY_D"):
    """"""


class SpellbookConfirmDeleteCallback(SpellbookReadCallback, prefix="BOOK_D"):
    spell_id: int


class ChatSettingsAddFilterCallback(CallbackData, prefix="SETTINGS_ADD"):
    rulebook_id: int


class ChatSettingsRemoveFilterCallback(CallbackData, prefix="SETTINGS_REMOVE"):
    rulebook_id: int


class EmptyCallback(CallbackData, prefix="IGNORE"):
    """"""
