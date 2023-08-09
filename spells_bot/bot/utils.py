import logging
from string import ascii_lowercase


# Allow alphabet + space + roman numbers
RU_CHARACTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя" + " " + "ivx"
EN_CHARACTERS = ascii_lowercase + " " + "ivx"


def create_logger(
    name: str,
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level: str = "INFO",
) -> logging.Logger:
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    logger.setLevel(level)

    return logger


def clean_spell_search_query(raw_query: str):
    """Cleans up and returns either ru name or en name

    Args:
        raw_query: search text

    Returns:
        tuple of either (ru_name, None) or (None, en_name)

    Raises:
         ValueError: if impossible to detect language or query is empty
    """
    query = raw_query.lower().strip()

    ru_name = en_name = None
    if all(char in RU_CHARACTERS for char in query):
        ru_name = query
    elif all(char in EN_CHARACTERS for char in query):
        en_name = query
    else:
        raise ValueError("Query must be in either english or russian")

    if not (ru_name or en_name):
        raise ValueError("Empty query")

    return ru_name, en_name
