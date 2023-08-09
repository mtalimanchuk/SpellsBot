from typing import List

from pydantic import BaseModel, field_validator


class ErrorResponse(BaseModel):
    message: str
    title: str


class BotClassInfo(BaseModel):
    alias: str
    description: str
    id: int
    name: str
    spellLevels: List[int] | None = None
    tableFeatures: str | None = None
    tableSpellCount: str | None = None

    @field_validator("*")
    def convert_empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class BotBook(BaseModel):
    id: int
    name: str


class BookForBotSpellList(BaseModel):
    abbreviation: str
    alias: str
    id: int
    name: str
    order: int


class ClassForBotSpellList(BaseModel):
    alias: str
    id: int
    level: int
    name: str


class Helper(BaseModel):
    alias: str | None = None
    isMain: bool
    name: str


class NameAlias(BaseModel):
    alias: str
    name: str


class SchoolForList(BaseModel):
    alias: str
    name: str
    type: NameAlias


class BotSpellInfo(BaseModel):
    id: int
    alias: str
    name: str
    engName: str
    shortDescription: str
    classes: List["ClassForBotSpellList"]
    shortDescriptionComponents: str | None = None
    area: str | None = None
    book: BookForBotSpellList | None = None
    castingTime: str | None = None
    components: str | None = None
    description: str | None = None
    duration: str | None = None
    effect: str | None = None
    helpers: List[Helper] | None = None
    races: List[NameAlias] | None = None
    range: str | None = None
    savingThrow: str | None = None
    spellResistance: int | None = None
    school: SchoolForList | None = None
    subSchool: str | None = None
    target: str | None = None

    @field_validator("*")
    def convert_empty_string_to_none(cls, v):
        if v == "":
            return None
        return v
