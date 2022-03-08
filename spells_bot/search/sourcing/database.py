from typing import List, Generator, Optional, Dict, Iterable, Union, Tuple

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    update,
    and_,
    asc,
    UnicodeText,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from spells_bot.config import DatabaseSettings
from spells_bot.search.sourcing.datatypes import (
    ShortSpellInfo,
    ExtendedSpellInfo,
    SpellTable,
    ChatSettings,
    ClassInfo,
    SchoolInfo,
    ClassInfoSpellRestriction,
    BasicShortSpellInfo,
)
from spells_bot.utils.log import create_logger

logger = create_logger("database")

Base = declarative_base()


class ShortSpellInfoRecord(Base):
    __tablename__ = "short_spell_info"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True)
    short_description_components = Column(String)
    book_abbreviation = Column(String)
    book_alias = Column(String)
    short_description = Column(String)
    schools = Column(JSON)
    classes = Column(JSON)
    name = Column(UnicodeText)
    is_race_spell = Column(Boolean)

    extended_spell_info = relationship(
        "ExtendedSpellInfoRecord", back_populates="short_spell_info", uselist=False
    )


class ExtendedSpellInfoRecord(Base):
    __tablename__ = "extended_spell_info"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    school = Column(String)
    variables = Column(JSON)
    text = Column(String)
    short_spell_info_id = Column(
        Integer, ForeignKey("short_spell_info.id"), unique=True
    )

    short_spell_info = relationship(
        "ShortSpellInfoRecord", back_populates="extended_spell_info"
    )
    tables = relationship("SpellTableRecord", back_populates="extended_spell_info")


class SpellTableRecord(Base):
    __tablename__ = "spell_table"

    id = Column(Integer, primary_key=True, index=True)
    html = Column(String)
    url = Column(String, default="")
    path = Column(String, default="")
    extended_spell_info_id = Column(Integer, ForeignKey("extended_spell_info.id"))

    extended_spell_info = relationship(
        "ExtendedSpellInfoRecord", back_populates="tables"
    )


class ClassRecord(Base):
    __tablename__ = "class"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True)
    book_abbreviation = Column(String, default="")
    book_alias = Column(String, default="")
    short_description = Column(String, default="")
    name = Column(UnicodeText, unique=True, index=True)
    is_own_spell_list = Column(Boolean, nullable=True)
    max_spell_lvl = Column(Integer, nullable=True)
    parent_class_ids = Column(JSON)


class SchoolRecord(Base):
    __tablename__ = "school"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(UnicodeText, index=True)
    type_id = Column(Integer)
    type_name = Column(UnicodeText)


class ChatSettingsRecord(Base):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True)
    book_filter = Column(JSON)


def init_db(sqlalchemy_database_url: str, drop: bool = False) -> sessionmaker:
    engine = create_engine(sqlalchemy_database_url)
    session_callable = sessionmaker(bind=engine)

    if drop:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)

    return session_callable


class Database:
    def __init__(self, settings: DatabaseSettings, drop_on_startup: bool = False):
        self._settings = settings
        self._db = init_db(settings.sqlalchemy_url, drop_on_startup)

    @staticmethod
    def _create_or_update_registry_item(
        db: Session,
        db_item_type,
        item: Union[ShortSpellInfo, ClassInfo, SchoolInfo],
        where_db: str,
        where_item: str,
    ):
        """Wrapper over try: add, except not unique: update existing

        :param db: sqlalchemy session
        :param db_item_type: database class for this item
        :param item: an instance of pydantic model
        :param where_db: name of database item attribute for equality comparison
        :param where_item: name of pydantic item attribute for equality comparison
        :return:
        """
        try:
            db.add(db_item_type(**item.to_orm()))
            db.commit()
        except IntegrityError:
            db.rollback()
            stmt_update = (
                update(db_item_type)
                .where(getattr(db_item_type, where_db) == getattr(item, where_item))
                .values(item.to_orm())
            )
            db.execute(stmt_update)
            db.commit()

    @staticmethod
    def _iter_classes(
        db: Session, book_filter: list = None
    ) -> Generator[ClassInfo, None, None]:
        if book_filter:
            classes = (
                db.query(ClassRecord)
                .where(ClassRecord.book_alias.in_(book_filter))
                .all()
            )
        else:
            classes = db.query(ClassRecord).all()

        for c in classes:
            yield ClassInfo.from_orm(c)

    @staticmethod
    def _create_or_update_classes(db: Session, classes: List[ClassInfo]):
        for c in classes:
            Database._create_or_update_registry_item(db, ClassRecord, c, "id", "id")

    @staticmethod
    def _iter_schools(db: Session) -> Generator[SchoolInfo, None, None]:
        for s in db.query(SchoolRecord).all():
            yield SchoolInfo.from_orm(s)

    @staticmethod
    def _create_or_update_schools(db: Session, schools: List[SchoolInfo]):
        for s in schools:
            Database._create_or_update_registry_item(db, SchoolRecord, s, "id", "id")

    @staticmethod
    def _create_or_update_spells(db: Session, spells: List[ShortSpellInfo]):
        for s in spells:
            Database._create_or_update_registry_item(
                db, ShortSpellInfoRecord, s, "alias", "alias"
            )

    @staticmethod
    def _convert_short_spell_info_rows(db: Session, rows: List[ShortSpellInfoRecord]):
        id2class = {c.id: c for c in Database._iter_classes(db)}
        id2school = {s.id: s for s in Database._iter_schools(db)}

        for result in rows:
            schools = [id2school[s] for s in result.schools]
            classes = []
            for c, lvl in result.classes.items():
                class_info = id2class[int(c)]
                class_info_restriction = ClassInfoSpellRestriction(
                    **class_info.dict(), level=lvl
                )
                classes.append(class_info_restriction)

            basic_spell_info = BasicShortSpellInfo.from_orm(result)
            yield ShortSpellInfo(
                **basic_spell_info.dict(), classes=classes, schools=schools
            )

    @staticmethod
    def _iter_rulebooks(db: Session) -> Generator[str, None, None]:
        for book_alias in db.query(ShortSpellInfoRecord.book_alias).distinct():
            yield book_alias[0]

    @staticmethod
    def _get_chat_settings(db: Session, chat_id: int) -> ChatSettingsRecord:
        return (
            db.query(ChatSettingsRecord)
            .filter(ChatSettingsRecord.chat_id == chat_id)
            .first()
        )

    @staticmethod
    def _create_chat_settings(
        db: Session, chat_id: int, book_filter: Dict[str, bool] = None
    ) -> ChatSettingsRecord:
        def _default_book_filter(book_alias_list: Iterable[str]):
            book_filter = {book: False for book in book_alias_list}
            book_filter["coreRulebook"] = True
            book_filter["advancedPlayerGuide"] = True
            return book_filter

        book_filter = book_filter or _default_book_filter(Database._iter_rulebooks(db))
        chat_settings = ChatSettingsRecord(chat_id=chat_id, book_filter=book_filter)

        db.add(chat_settings)
        db.commit()
        db.refresh(chat_settings)

        return chat_settings

    @staticmethod
    def _get_or_create_chat_settings(
        db: Session, chat_id: int, book_filter: Dict[str, bool] = None
    ) -> ChatSettingsRecord:
        chat_settings = Database._get_chat_settings(db, chat_id)

        if not chat_settings:
            chat_settings = Database._create_chat_settings(db, chat_id)

        return chat_settings

    @staticmethod
    def _get_book_filter(db: Session, chat_id: int = None):
        if chat_id:
            chat_settings = Database._get_or_create_chat_settings(db, chat_id)
            include_books = [k for k, v in chat_settings.book_filter.items() if v]
        else:
            include_books = list(Database._iter_rulebooks(db))

        return include_books

    def has_spell_list(self, min_n: int = 1000):
        """Check if there are at least ``min_n`` spells.
        Use it to check if you need to update registry

        :param min_n: min number of spells to return True
        :return:
        """
        with self._db() as db:
            short_spell_info_count = db.query(ShortSpellInfoRecord).count()

        return short_spell_info_count > min_n

    def create_or_update_registry(
        self,
        spells: List[ShortSpellInfo],
        classes: List[ClassInfo],
        schools: List[SchoolInfo],
    ):
        """Create or update short spell info, class and school tables
        with provided values

        :param spells: list of ShortSpellInfo objects
        :param classes: list of ClassInfo objects
        :param schools: list of SchoolInfo objects
        :return:
        """
        with self._db() as db:
            self._create_or_update_classes(db, classes)
            self._create_or_update_schools(db, schools)
            self._create_or_update_spells(db, spells)

    def iter_short_spell_info_by_name(
        self, name: str, chat_id: int = None
    ) -> Generator[ShortSpellInfo, None, None]:
        """Yield short spell info filtering by name and chat's book filter if chat_id is provided

        :param name: spell name in cyrillic
        :param chat_id: if provided and not found in database, will create a default filter
        :return:
        """

        with self._db() as db:
            include_books = self._get_book_filter(db, chat_id)

            rows = (
                db.query(ShortSpellInfoRecord)
                .where(ShortSpellInfoRecord.book_alias.in_(include_books))
                .order_by(asc(ShortSpellInfoRecord.name))
                .all()
            )

            for result in self._convert_short_spell_info_rows(db, rows):
                if name in result.name.lower():
                    yield result

    def iter_short_spell_info_by_class_level(
        self, class_id: int, spell_level: int, chat_id: int = None
    ) -> Generator[ShortSpellInfo, None, None]:
        """Yield short spell info filtering by class, spell level restriction,
        and chat's book filter if chat_id is provided

        :param class_id: class id
        :param spell_level: spell circle level
        :param chat_id: if provided and not found in database, will create a default filter
        :return:
        """

        with self._db() as db:
            include_books = self._get_book_filter(db, chat_id)

            rows = (
                db.query(ShortSpellInfoRecord)
                .where(
                    and_(
                        ShortSpellInfoRecord.classes[str(class_id)].as_integer()
                        == spell_level,
                        ShortSpellInfoRecord.book_alias.in_(include_books),
                    )
                )
                .order_by(asc(ShortSpellInfoRecord.name))
                .all()
            )

            yield from self._convert_short_spell_info_rows(db, rows)

    def get_class(self, class_id: int) -> ClassInfo:
        with self._db() as db:
            c = db.query(ClassRecord).where(ClassRecord.id == class_id).first()
        return ClassInfo.from_orm(c)

    def iter_classes(self, chat_id: int):
        with self._db() as db:
            include_books = self._get_book_filter(db, chat_id)
            yield from self._iter_classes(db, include_books)

    def iter_levels(self, class_id: int) -> Generator[int, None, None]:
        class_id_str = str(class_id)
        with self._db() as db:
            rows = (
                db.query(ShortSpellInfoRecord)
                .where(ShortSpellInfoRecord.classes[class_id_str].as_integer() >= 0)
                .all()
            )

            unique_levels = set()
            for r in rows:
                unique_levels.add(r.classes[class_id_str])

            yield from unique_levels

    def iter_rulebooks(self) -> Generator[str, None, None]:
        """Yield rulebook aliases in camelCase

        :return:
        """
        with self._db() as db:
            yield from self._iter_rulebooks(db)

    def get_full_spell_info(
        self, spell_alias: str
    ) -> Tuple[ShortSpellInfo, Optional[ExtendedSpellInfo]]:
        extended_spell_info = None

        with self._db() as db:
            short_spell_info = (
                db.query(ShortSpellInfoRecord)
                .filter(ShortSpellInfoRecord.alias == spell_alias)
                .first()
            )

            if short_spell_info:
                extended_spell_info = short_spell_info.extended_spell_info

                if extended_spell_info:
                    extended_spell_info = ExtendedSpellInfo.from_orm(
                        extended_spell_info
                    )

        return short_spell_info, extended_spell_info

    def get_extended_spell_info(self, spell_alias: str) -> Optional[ExtendedSpellInfo]:
        """Get extended spell info by english alias if it exists

        :param spell_alias: spell name in ascii
        :return:
        """
        _, extended_spell_info = self.get_full_spell_info(spell_alias)
        return extended_spell_info

    def create_extended_spell_info(
        self,
        spell_alias: str,
        extended_spell_info: ExtendedSpellInfo,
        tables: List[SpellTable],
    ) -> ExtendedSpellInfo:
        tables = [SpellTableRecord(**t.to_orm()) for t in tables]

        with self._db() as db:
            short_spell_info = (
                db.query(ShortSpellInfoRecord)
                .filter(ShortSpellInfoRecord.alias == spell_alias)
                .first()
            )
            extended_spell_info = ExtendedSpellInfoRecord(
                **extended_spell_info.to_orm(),
                tables=tables,
                short_spell_info=short_spell_info,
            )
            db.add(extended_spell_info)
            db.commit()
            db.refresh(extended_spell_info)
            extended_spell_info = ExtendedSpellInfo.from_orm(extended_spell_info)

        return extended_spell_info

    def get_or_create_chat_settings(self, chat_id: int) -> ChatSettings:
        with self._db() as db:
            chat_settings = self._get_or_create_chat_settings(db, chat_id)
            chat_settings = ChatSettings.from_orm(chat_settings)

        return chat_settings

    def update_book_filter(self, chat_id: int, book_alias: str) -> ChatSettings:
        with self._db() as db:
            chat_settings = self._get_or_create_chat_settings(db, chat_id)

            new_book_filter = chat_settings.book_filter
            new_book_filter[book_alias] = not new_book_filter[book_alias]

            stmt_update = (
                update(ChatSettingsRecord)
                .where(ChatSettingsRecord.chat_id == chat_id)
                .values(book_filter=new_book_filter)
            )
            db.execute(stmt_update)
            db.commit()
            db.refresh(chat_settings)
            chat_settings = ChatSettings.from_orm(chat_settings)

        return chat_settings
