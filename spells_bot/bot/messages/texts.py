import warnings
from typing import Sequence

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from spells_bot.config import settings
from spells_bot.pathfinder_api.schemas import BotClassInfo, BotSpellInfo

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def _validate_message_len(msg: str):
    """Validate message length against telegram API limits

    Args:
        msg: text to be validated. Any markup should be included in the string

    Returns:
        True if text can fit in one telegram message, False otherwise
    """
    return len(msg.encode("utf-8")) < 4096


def _menu_message_header(text: str):
    return f"<b>{text}</b>\n\n"


def start_main():
    return (
        f"{_menu_message_header('📖 Книга Заклинаний Pathfinder 1e 🔮')}"
        "/spellbook - открыть мою книгу\n"
        "/help - как пользоваться книгой\n"
        "/menu - поиск по классам\n"
        "/settings - настройки поиска\n"
    )


def help_main(bot_name: str):
    return (
        f"{_menu_message_header('📖 Как пользоваться книгой ℹ')}"
        "В этой книге можно искать и записывать заклинания.\n\n"
        f"Начните писать\n\n<code>@{bot_name} название заклинания</code>\n\n"
        "в любом чате, выберите нужный результат и полное описание заклинания отправится в текущий чат.\n"
        "Его можно будет записать в свою книгу избранных заклинаний, которая открывается по команде /spellbook\n\n"
        "Для поиска доступных заклинаний для определенного класса, перейдите в /menu.\n\n"
        "Настройте фильтр по книгам правил в /settings или во время поиска, выбрав результат внизу списка."
    )


def menu_main():
    return f"{_menu_message_header('📖 Поиск по классам 🔮')}"


def menu_class(class_: BotClassInfo):
    header = _menu_message_header(f"📖 {class_.name} 🔮")
    return f"{header}<i>{class_.description}</i>"


def menu_class_spell_level(class_: BotClassInfo, spells: Sequence[BotSpellInfo], spell_level: int):
    spell_description_pages = []
    header = _menu_message_header(f"{class_.name} {spell_level} круг")
    current_page = header

    for s in spells:
        spell_line = f"<u>{s.name}</u>: <i>{s.shortDescription}</i>"
        possible_current_page = "\n".join([current_page, spell_line])

        if _validate_message_len(possible_current_page):
            current_page = possible_current_page
        else:
            spell_description_pages.append(current_page)
            current_page = "\n".join([header, spell_line])

    spell_description_pages.append(current_page)

    return spell_description_pages


def spellbook_empty():
    return 'Книга заклинаний пуста\n\nВыберите нужное заклинание через поиск и нажмите "Добавить в книгу заклинаний"'


def spellbook_main(spell: BotSpellInfo, extended: bool):
    tables = None
    if extended:
        text, tables = extended_description_message(spell)
    else:
        text = short_description_message_with_optional_values(spell)
    return text, tables


def spellbook_main_after_delete_spell():
    return "Удалено"


def settings_main(bot_name: str):
    return (
        f"{_menu_message_header('📖 Настройки поиска ⚙')}"
        "Выберите книги правил, в которых хотите искать заклинания. "
        f"Настройки распространяются на /menu и поиск через @{bot_name}. "
    )


def _insert_into_html_template(html: str):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Title</title>
    </head>
    <body>
        {html}
    </body>
    </html>
    """


def _remove_fraction_values_from_table(soup: BeautifulSoup):
    soup.find("a", {"class": "changeFraction"}).extract()

    for fraction_hidden in soup.find_all("span", {"class": "fraction hidden"}):
        fraction_hidden.extract()


def _remove_html_tags(html: str, keep_links: bool):
    soup = BeautifulSoup(html, "html.parser")

    table_divs = soup.find_all("div", {"class": "tableBlock"})
    tables = []
    for div in table_divs:
        t = div.extract()
        tables.append(str(t))

    subheader_spans = soup.find_all("span", {"class": "textSubheader"})
    for span in subheader_spans:
        new_tag = soup.new_tag("i")
        new_tag.string = span.text
        span.replace_with(new_tag)

    dfn_tags = soup.find_all("dfn")
    for dfn_tag in dfn_tags:
        new_tag = soup.new_tag("i")
        new_tag.string = dfn_tag.text
        dfn_tag.replace_with(new_tag)

    ul_tags = soup.find_all("ul")
    for ul in ul_tags:
        for li in ul.find_all_next("li"):
            li.replace_with(f"- {li.text}")
        ul.replace_with(ul.text)

    a_tags = soup.find_all("a")
    for a_tag in a_tags:
        if keep_links:
            a_tag["href"] = f"{settings.api.base_web_url}{a_tag['href']}"
        else:
            a_tag.replace_with(a_tag.text)

    clean_html = str(soup)

    return clean_html, tables


def _make_header(spell: BotSpellInfo):
    helpers = []
    if spell.helpers:
        for h in spell.helpers:
            if h.alias:
                helper = f'<a href="{h.alias}">{h.name}</a>'
            else:
                helper = h.name
            helpers.append(helper)

    if helpers:
        helpers_line = "\nПеревод: " + ", ".join(helpers) + "\n"
    else:
        helpers_line = ""

    return f"<b>{spell.name.upper()}</b> ({spell.engName.upper()})\n{spell.school.name}\n{helpers_line}"


def _make_optional_values(spell: BotSpellInfo):
    optional_rows = []

    if spell.spellResistance:
        if spell.spellResistance == 0:
            spell_resistance = "Нет"
        elif spell.spellResistance == 1:
            spell_resistance = "Да"
        else:
            spell_resistance = spell.spellResistance
    else:
        spell_resistance = None

    value_map = {
        f"Источник": spell.book.name,
        f"Круг": ", ".join(c.name + " " + str(c.level) for c in spell.classes),
        f"Время сотворения": spell.castingTime,
        f"Компоненты": spell.components,
        f"Дистанция": spell.area,
        f"Эффект": spell.effect,
        f"Цель": spell.target,
        f"Длительность": spell.duration,
        f"Испытание": spell.savingThrow,
        f"Устойчивость к магии": spell_resistance,
    }
    for k, v in value_map.items():
        if v is not None:
            optional_rows.append(f"<b>{k}</b>: {v}")
    return "\n".join(optional_rows)


def _make_extended_description(spell: BotSpellInfo):
    return _remove_html_tags(spell.description, keep_links=True)


def _make_short_description(spell: BotSpellInfo, keep_links: bool):
    clean_html, _ = _remove_html_tags(spell.shortDescription, keep_links=keep_links)
    return clean_html


def class_table_feature(class_: BotClassInfo):
    soup = BeautifulSoup(class_.tableFeatures, "html.parser")

    _remove_fraction_values_from_table(soup)

    clean_html = str(soup)
    return clean_html


def class_table_spell_count(class_: BotClassInfo):
    soup = BeautifulSoup(class_.tableSpellCount, "html.parser")

    clean_html = str(soup)
    return clean_html


def short_description_message(spell: BotSpellInfo, keep_links: bool):
    text = _make_short_description(spell, keep_links=keep_links)

    return text


def short_description_message_with_optional_values(spell: BotSpellInfo):
    text = f"{_make_header(spell)}\n{_make_short_description(spell, keep_links=True)}\n\n{_make_optional_values(spell)}"

    return text


def extended_description_message(spell: BotSpellInfo):
    extended_description, tables = _make_extended_description(spell)
    text = "\n\n".join([_make_header(spell), _make_optional_values(spell), extended_description])

    if not _validate_message_len(text):
        text = short_description_message_with_optional_values(spell)
        text = (
            f"{text}\n\n"
            "Полное описание заклинания слишком длинное, чтобы уместить его в сообщение - перейдите по ссылке на сайт."
        )

    return text, tables


def empty_inline_results_message(query: str):
    return (
        f'По запросу "{query[:100]}" ничего не найдено.\n\n'
        "Проверьте фильтр по книгам в меню /settings "
        "и удостоверьтесь, что вы вводите название заклинания либо на русском, либо на английском языке."
    )


def toast_drawing_tables():
    return "Рисую таблицы, это может занять несколько секунд"
