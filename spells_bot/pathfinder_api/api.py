import ssl
from operator import attrgetter
from typing import Sequence

import aiohttp

from spells_bot.config import settings
from spells_bot.pathfinder_api import schemas


class ApiError(Exception):
    def __init__(self, message: str, error: schemas.ErrorResponse):
        super().__init__(message)

        self.error = error


CACHE_MAX_SIZE = 100
TTL_SECONDS = 60 * 10


class HttpClient:
    session: aiohttp.ClientSession | None = None

    def start(self):
        self.session = aiohttp.ClientSession()

    async def stop(self):
        await self.session.close()
        self.session = None


async def _make_request(session: aiohttp.ClientSession, endpoint: str, params: dict):
    params_refined = {}

    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, bool):
            v = str(v).lower()
        if isinstance(v, list):
            v = ",".join(str(item) for item in v)

        params_refined[k] = v

    url = f"{settings.api.base_api_url}/{endpoint}"
    async with session.get(url, params=params_refined, ssl=ssl.SSLContext()) as response:
        if response.status != 200:
            error_response = await response.json()
            raise ApiError(f"Pathfinder API error: {error_response}", error_response)

        data = await response.json()

    return data


async def get_class(session: aiohttp.ClientSession, class_id: int, extended: bool = False, magical_only: bool = None):
    classes = await _make_request(
        session, "classes", {"id": class_id, "extended": extended, "magicClass": magical_only}
    )
    class_ = classes[0]

    return schemas.BotClassInfo(**class_)


async def get_classes(session: aiohttp.ClientSession, extended: bool = False, magical_only: bool = None):
    classes = []

    for class_ in await _make_request(session, "classes", {"extended": extended, "magicClass": magical_only}):
        classes.append(schemas.BotClassInfo(**class_))

    return classes


async def get_rulebooks(session: aiohttp.ClientSession, with_spells: bool = False):
    rulebooks = []

    for class_ in await _make_request(session, "rulebooks", {"withSpells": with_spells}):
        rulebooks.append(schemas.BotBook(**class_))

    return sorted(rulebooks, key=attrgetter("id"))


async def get_spells(
    session: aiohttp.ClientSession,
    ru_name: str = None,
    en_name: str = None,
    class_id: int = None,
    alias: str = None,
    level: int = None,
    rulebook_ids: Sequence[int] = None,
    extended: bool = False,
):
    spells = []

    for spell in await _make_request(
        session,
        "spells",
        {
            "name": ru_name,
            "engName": en_name,
            "classId": class_id,
            "alias": alias,
            "level": level,
            "rulebookIds": rulebook_ids,
            "extended": extended,
        },
    ):
        spells.append(schemas.BotSpellInfo(**spell))

    spells.sort(key=attrgetter("name"))
    return spells


# @ttl_cache(maxsize=CACHE_MAX_SIZE, ttl=TTL_SECONDS)
async def get_spell(session: aiohttp.ClientSession, spell_id: int, extended: bool = False):
    spells = await _make_request(session, "spells", {"id": spell_id, "extended": extended})
    spell = spells[0]
    return schemas.BotSpellInfo(**spell)
