#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from pathlib import Path

from telegram import Update
from telegram.ext import (
    CallbackContext,
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackQueryHandler,
)

from spells_bot.config import BotSettings
from spells_bot.responder import Responder
from spells_bot.utils.log import create_logger


logger = create_logger("SpellsBot")


def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    try:
        chat_id = update.effective_user.id
        spell_id = context.args[0]

        context.bot.send_media_group(**responder.send_spell_tables(chat_id, spell_id))
    except IndexError:
        update.message.reply_text(**responder.greet())


def help(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text(**responder.help())


def inline_query(update: Update, context: CallbackContext):
    """Handle the inline query."""
    chat = update.inline_query.from_user["username"]
    chat_id = update.inline_query.from_user.id
    query = update.inline_query.query.lower().strip()

    if not query:
        return

    logger.info(f'User @{chat} [{chat_id}] searched "{query}"')

    update.inline_query.answer(**responder.inline_search(query, chat_id))


def menu(update: Update, context: CallbackContext):
    """Send main menu message"""
    chat_id = update.effective_user.id
    update.message.reply_text(**responder.menu(chat_id))


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
    cmd = Responder.decode_callback(update.callback_query.data)
    chat_id = update.callback_query.from_user.id

    update.effective_message.edit_text(**responder.menu(chat_id))
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
    cmd, class_id, level, page = Responder.decode_callback(update.callback_query.data)
    chat_id = update.callback_query.from_user.id

    update.effective_message.edit_text(
        **responder.menu_level(class_id, level, chat_id, page)
    )
    update.callback_query.answer("")


def search_settings_callback(update: Update, context: CallbackContext):
    cmd, book = Responder.decode_callback(update.callback_query.data)
    chat_id = update.callback_query.from_user.id

    update.callback_query.edit_message_reply_markup(
        **responder.update_search_settings(chat_id, book)
    )
    update.callback_query.answer(f"Updated settings for {chat_id}")


def pass_callback(update: Update, context: CallbackContext):
    update.callback_query.answer("")


def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f"Update {update} caused error {context.error}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-e", "--env", type=Path, required=True)
    options = parser.parse_args()

    settings = BotSettings()

    updater = Updater(settings.telegram.bot_token)
    responder = Responder(settings, updater.bot.link)

    h = updater.dispatcher.add_handler
    eh = updater.dispatcher.add_error_handler

    h(CommandHandler("start", start))
    h(CommandHandler("help", help))
    h(CommandHandler("menu", menu))
    h(InlineQueryHandler(inline_query))
    h(CallbackQueryHandler(search_settings_callback, pattern=r"SETTINGS"))
    h(CallbackQueryHandler(tables_callback, pattern=r"TABLE:.*"))
    h(CallbackQueryHandler(home_callback, pattern=r"^HOME"))
    h(CallbackQueryHandler(class_callback, pattern=r"CLASS:.*"))
    h(CallbackQueryHandler(class_info_callback, pattern=r"CLASSINFO:.*"))
    h(CallbackQueryHandler(level_callback, pattern=r"LEVEL:.*"))
    h(CallbackQueryHandler(pass_callback, pattern=r"^PASS$"))
    eh(error)

    updater.start_polling()
    logger.info("BOT DEPLOYED. Ctrl+C to terminate")

    updater.idle()
