import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.methods import EditMessageReplyMarkup, SendMediaGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InputMediaPhoto,
    FSInputFile,
)
from sqlalchemy.exc import IntegrityError

from spells_bot.bot import utils
from spells_bot.bot.callback_schema import (
    BaseClassesCallback,
    SpellbookReadCallback,
    SpellbookCreateCallback,
    SpellbookPromptDeleteCallback,
    SpellbookConfirmDeleteCallback,
    EmptyCallback,
    ChatSettingsAddFilterCallback,
    ChatSettingsRemoveFilterCallback,
    MenuClassCallback,
    ClassesTableCallback,
    ClassesSpellsCallback,
    SpellTablesCallback,
)
from spells_bot.bot.config import settings
from spells_bot.bot.messages import views, texts
from spells_bot.bot.messages import keyboards
from spells_bot.database.models import (
    get_db,
    get_or_create_user,
    get_saved_spells,
    create_saved_spell,
    delete_saved_spell,
    get_saved_spell_by_index,
    get_chat_settings,
    chat_settings_add_rulebook,
    chat_settings_remove_rulebook,
)
from spells_bot.image_generator import HtmlToImage
from spells_bot.pathfinder_api import api

router = Router()


api_client = api.HttpClient()


@router.startup()
async def on_startup():
    """"""
    logging.info("API session started")
    api_client.start()


@router.shutdown()
async def on_shutdown():
    """"""
    logging.info("API session stopped")
    await api_client.stop()


@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    """
    This handler receive messages with `/start` command
    """
    # Most event objects have aliases for API methods that can be called in events' context
    # For example if you want to answer to incoming message you can use `message.answer(...)` alias
    # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
    # method automatically or call API method directly via
    # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
    # await message.answer(f"Hello, <b>{message.from_user.full_name}!</b>")
    # Create a keyboard with a single button
    with get_db() as db:
        user = get_or_create_user(db, message.from_user.id)
        text, keyboard = views.start_main()

    await message.answer(text=text, reply_markup=keyboard)


@router.message(Command(commands=["help"]))
async def command_menu_handler(message: Message, bot: Bot) -> None:
    """
    This handler receive messages with `/help` command
    """
    bot_user = await bot.me()
    text, markup = views.help_main(bot_user.username)
    await message.answer(text=text, reply_markup=markup)


@router.message(Command(commands=["menu"]))
async def command_menu_handler(message: Message) -> None:
    """
    This handler receive messages with `/menu` command
    """
    classes = await api.get_classes(api_client.session, extended=True, magical_only=True)
    text, markup = views.menu_main(classes)
    await message.answer(text=text, reply_markup=markup)


@router.message(Command(commands=["spellbook"]))
async def command_spellbook_handler(message: Message) -> None:
    """
    This handler receive messages with `/spellbook` command
    """
    with get_db() as db:
        saved_spells = get_saved_spells(db, message.from_user.id)

        try:
            spell_id = saved_spells[0].spell_id
        except IndexError:
            text, keyboard = views.spellbook_empty()
            await message.answer(text=text, reply_markup=keyboard)
            return

        spell_data = await api.get_spell(api_client.session, spell_id, extended=True)

        text, keyboard = views.spellbook_main(
            index=0,
            index_max=len(saved_spells),
            spell=spell_data,
        )

    await message.answer(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@router.message(Command(commands=["settings"]))
async def command_settings_handler(message: Message, bot: Bot) -> None:
    with get_db() as db:
        chat_settings = get_chat_settings(db, message.from_user.id)
        user_rulebooks = chat_settings.book_filter

    all_rulebooks = await api.get_rulebooks(api_client.session, with_spells=True)

    bot_user = await bot.me()
    text, keyboard = views.settings_main(all_rulebooks, user_rulebooks, bot_user.username)

    await message.answer(text=text, reply_markup=keyboard)


@router.message(~(F.via_bot | F.from_user.is_bot))
async def any_text_message_handler(message: Message) -> None:
    text, keyboard = views.any_text_message(message.text)
    await message.answer(text=text, reply_markup=keyboard)


@router.inline_query()
async def inline_search(inline_query: types.InlineQuery):
    with get_db() as db:
        chat_settings = get_chat_settings(db, inline_query.from_user.id)
        user_rulebooks = chat_settings.book_filter

    try:
        ru_name, en_name = utils.clean_spell_search_query(inline_query.query)
    except ValueError as e:
        logging.info(f"Ignored query {inline_query.query} ({e})")
        spells = []
    else:
        spells = await api.get_spells(
            api_client.session, ru_name=ru_name, en_name=en_name, extended=True, rulebook_ids=user_rulebooks
        )
        logging.info(
            f'User @{inline_query.from_user.username} [{inline_query.from_user.id}] searched "{inline_query.query}"'
        )

    all_rulebooks = await api.get_rulebooks(api_client.session, with_spells=True)

    await inline_query.answer(
        results=views.inline_results(
            inline_query.query, spells, all_rulebooks, user_rulebooks, inline_query.from_user.id
        )
    )


@router.callback_query(SpellTablesCallback.filter())
async def spell_tables_callback(query: CallbackQuery, callback_data: SpellTablesCallback, bot: Bot):
    await query.answer(texts.toast_drawing_tables())

    spell = await api.get_spell(api_client.session, callback_data.spell_id, extended=True)
    text, tables = texts.extended_description_message(spell)

    hti = HtmlToImage(settings.storage.data_root_dir, settings.hti.css_file)
    spell_table_images = hti.spell_tables(tables, spell_alias=spell.alias)

    media_group = []
    for image_idx, image_path in enumerate(spell_table_images):
        photo = InputMediaPhoto(
            media=FSInputFile(image_path), caption=f"<b>{spell.name.upper()}</b> <i>таблица {image_idx + 1}</i>"
        )
        media_group.append(photo)

    await bot(SendMediaGroup(chat_id=query.from_user.id, media=media_group))


@router.callback_query(ChatSettingsAddFilterCallback.filter())
async def chat_settings_add_rulebook_callback(
    query: CallbackQuery, callback_data: ChatSettingsAddFilterCallback, bot: Bot
):
    with get_db() as db:
        chat_settings = chat_settings_add_rulebook(db, query.from_user.id, callback_data.rulebook_id)
        user_rulebooks = chat_settings.book_filter

    all_rulebooks = await api.get_rulebooks(api_client.session, with_spells=True)
    keyboard = keyboards.chat_settings(all_rulebooks, user_rulebooks)

    await query.answer()
    if query.message:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await bot(EditMessageReplyMarkup(inline_message_id=query.inline_message_id, reply_markup=keyboard))


@router.callback_query(ChatSettingsRemoveFilterCallback.filter())
async def chat_settings_remove_rulebook_callback(
    query: CallbackQuery, callback_data: ChatSettingsRemoveFilterCallback, bot: Bot
):
    with get_db() as db:
        chat_settings = chat_settings_remove_rulebook(db, query.from_user.id, callback_data.rulebook_id)
        user_rulebooks = chat_settings.book_filter

    all_rulebooks = await api.get_rulebooks(api_client.session, with_spells=True)
    keyboard = keyboards.chat_settings(all_rulebooks, user_rulebooks)

    await query.answer()
    if query.message:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await bot(EditMessageReplyMarkup(inline_message_id=query.inline_message_id, reply_markup=keyboard))


@router.callback_query(ClassesSpellsCallback.filter())
async def classes_with_id_spell_level_callback(query: CallbackQuery, callback_data: ClassesSpellsCallback):
    await query.answer()

    with get_db() as db:
        chat_settings = get_chat_settings(db, query.from_user.id)
        user_rulebooks = chat_settings.book_filter

    class_ = await api.get_class(api_client.session, callback_data.id, extended=True, magical_only=True)
    spells = await api.get_spells(
        api_client.session, class_id=class_.id, level=callback_data.spell_level, rulebook_ids=user_rulebooks
    )

    text, markup = views.menu_class_spell_level(
        class_, spells, active_spell_level=callback_data.spell_level, page=callback_data.page
    )
    await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(ClassesTableCallback.filter())
async def classes_with_id_tables_callback(query: CallbackQuery, callback_data: ClassesTableCallback):
    await query.answer(texts.toast_drawing_tables())

    class_ = await api.get_class(api_client.session, callback_data.id, extended=True, magical_only=True)
    text, markup = views.menu_class(class_, show_tables_button=False)

    hti = HtmlToImage(settings.storage.data_root_dir, settings.hti.css_file)

    class_tables = []
    if class_.tableFeatures:
        class_tables.append(texts.class_table_feature(class_))

    if class_.tableSpellCount:
        class_tables.append(texts.class_table_spell_count(class_))

    class_table_images = hti.class_tables(class_tables, class_.alias)

    await query.message.delete()
    await query.message.answer(f"📜 <b>{class_.name.upper()}</b> 📜")

    media_group = []
    for image_idx, image_path in enumerate(class_table_images):
        photo = InputMediaPhoto(
            media=FSInputFile(image_path), caption=f"<b>{class_.name.upper()}</b> <i>таблица {image_idx + 1}</i>"
        )
        media_group.append(photo)

    await query.message.answer_media_group(media=media_group)
    await query.message.answer(text=text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(BaseClassesCallback.filter())
async def classes_with_id_callback(query: CallbackQuery, callback_data: BaseClassesCallback):
    await query.answer()

    class_ = await api.get_class(api_client.session, callback_data.id, extended=True, magical_only=True)
    text, markup = views.menu_class(class_)

    await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(MenuClassCallback.filter())
async def classes_callback(query: CallbackQuery, callback_data: MenuClassCallback):
    await query.answer()

    classes = await api.get_classes(api_client.session, extended=False, magical_only=True)
    text, markup = views.menu_main(classes)
    await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(SpellbookReadCallback.filter())
async def spellbook_read_callback(query: CallbackQuery, callback_data: SpellbookReadCallback):
    await query.answer()

    with get_db() as db:
        try:
            spell, index_max = get_saved_spell_by_index(db, query.from_user.id, callback_data.index)
        except IndexError:
            await query.message.edit_text(
                text=f"No spell for index {callback_data.index}", disable_web_page_preview=True
            )
            return

        spell_data = await api.get_spell(api_client.session, spell.spell_id, extended=True)

        text, keyboard = views.spellbook_main(
            index=callback_data.index,
            index_max=index_max,
            spell=spell_data,
            extended=callback_data.extended,
        )

    await query.message.edit_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@router.callback_query(SpellbookCreateCallback.filter())
async def spellbook_create_callback(query: CallbackQuery, callback_data: SpellbookReadCallback, bot: Bot):
    with get_db() as db:
        try:
            create_saved_spell(db, query.from_user.id, callback_data.spell_id)
            spell_data = await api.get_spell(api_client.session, callback_data.spell_id, extended=True)

            await query.answer("Добавлено в книгу заклинаний")
            await bot(
                EditMessageReplyMarkup(
                    inline_message_id=query.inline_message_id,
                    reply_markup=keyboards.extended_description_message_saved_spell(spell_data),
                )
            )
        except IntegrityError:
            await query.answer("Заклинание уже есть в книге")


@router.callback_query(SpellbookPromptDeleteCallback.filter())
async def spellbook_prompt_delete_callback(query: CallbackQuery, callback_data: SpellbookPromptDeleteCallback):
    await query.answer("Стереть заклинание из книги?")
    with get_db() as db:
        spell, index_max = get_saved_spell_by_index(db, query.from_user.id, callback_data.index)
        spell_data = await api.get_spell(api_client.session, spell.spell_id, extended=callback_data.extended)

    keyboard = keyboards.spellbook_main_prompt_delete_spell(
        spell_data, callback_data.index, index_max, callback_data.extended
    )
    await query.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(SpellbookConfirmDeleteCallback.filter())
async def spellbook_delete_callback(query: CallbackQuery, callback_data: SpellbookConfirmDeleteCallback):
    with get_db() as db:
        delete_saved_spell(db, query.from_user.id, callback_data.spell_id)
        updated_index = callback_data.index - 1
        try:
            spell, index_max = get_saved_spell_by_index(db, query.from_user.id, updated_index)

            spell_data = await api.get_spell(api_client.session, spell.spell_id, extended=True)

            text, keyboard = views.spellbook_main(
                index=updated_index,
                index_max=index_max,
                spell=spell_data,
                extended=callback_data.extended,
            )
        except IndexError:
            text, keyboard = views.spellbook_empty()

    await query.answer("Вы стерли заклинание из книги")
    await query.message.edit_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@router.callback_query(EmptyCallback.filter())
async def empty_callback(query: CallbackQuery, callback_data: EmptyCallback):
    await query.answer()


async def main() -> None:
    # Dispatcher is a root router
    dp = Dispatcher()
    # ... and all other routers should be attached to Dispatcher
    dp.include_router(router)

    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(settings.telegram.bot_token, parse_mode="HTML")
    # And the run events dispatching
    await dp.start_polling(bot, on_startup=on_startup)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
