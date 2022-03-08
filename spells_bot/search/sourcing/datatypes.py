from pathlib import Path
from typing import List, Optional, Dict

from pydantic import BaseModel


class OrmSerializableBaseModel(BaseModel):
    """Base pydantic model with orm_mode enabled.


    ``.from_orm(...)`` is implemented by default when orm_mode = True

    ``.to_orm()`` is implemented for convenience
    and can be overridden in child models, e.g. to serialize ``Path``s

    """

    class Config:
        orm_mode = True

    def to_orm(self):
        return self.dict()


class SpellTable(OrmSerializableBaseModel):
    html: str
    url: Optional[str]
    path: Optional[Path]

    def to_orm(self):
        return {"html": self.html, "url": self.url, "path": str(self.path)}


class ClassInfo(OrmSerializableBaseModel):
    id: int
    alias: str = ""
    book_abbreviation: str = ""
    book_alias: str = ""
    short_description: str = ""
    name: str
    is_own_spell_list: Optional[bool]
    max_spell_lvl: Optional[int]
    parent_class_ids: list


class ClassInfoSpellRestriction(ClassInfo):
    level: int


class SchoolInfo(OrmSerializableBaseModel):
    id: int
    name: str
    type_id: int
    type_name: str


class BasicShortSpellInfo(OrmSerializableBaseModel):
    """Part of ShortSpellInfo which can be serialized from orm and to orm

    """
    alias: str
    short_description_components: str
    book_abbreviation: str
    book_alias: str
    short_description: str
    name: str
    is_race_spell: bool


class ShortSpellInfo(BasicShortSpellInfo):
    """Part of ShortSpellInfo which cannot be serialized from orm but can be serialized to orm

    """
    schools: List[SchoolInfo]
    classes: List[ClassInfoSpellRestriction]

    @classmethod
    def from_orm(cls, *args, **kwargs):
        raise NotImplementedError(f"{cls.__name__} should be instantiated with __init__ rather than from_orm")

    def to_orm(self):
        d = self.dict(exclude={"schools", "classes"})
        d["schools"] = [s.id for s in self.schools]
        d["classes"] = {c.id: c.level for c in self.classes}
        return d


class ExtendedSpellInfo(OrmSerializableBaseModel):
    full_name: str
    school: str
    variables: dict
    text: str
    tables: List[SpellTable]

    def to_orm(self):
        return {
            "full_name": self.full_name,
            "school": self.school,
            "variables": self.variables,
            "text": self.text,
        }


class ChatSettings(OrmSerializableBaseModel):
    chat_id: int
    book_filter: Dict[str, bool]

    def to_orm(self):
        return self.dict()
