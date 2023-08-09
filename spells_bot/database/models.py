from typing import List, Sequence

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    ForeignKey,
    update,
    select,
    delete,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from spells_bot.bot.config import settings
from spells_bot.bot.utils import create_logger

logger = create_logger("database")

Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True)

    chat_settings = relationship("ChatSettings", back_populates="user", uselist=False)
    saved_spells = relationship("SavedSpell", back_populates="user", uselist=True)


class ChatSettings(Base):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True)
    user = relationship("User", back_populates="chat_settings")
    book_filter = Column(JSON)


class SavedSpell(Base):
    __tablename__ = "saved_spell"

    __table_args__ = (UniqueConstraint("user_id", "spell_id", name="uq_user_spell"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User", back_populates="saved_spells")
    spell_id = Column(Integer)


def init_db(sqlalchemy_database_url: str, drop: bool = False) -> sessionmaker:
    """Create sqlalchemy sessionmaker

    :param sqlalchemy_database_url: currently tested only against sqlite
    :param drop: drop existing and recreate database if True
    :return:
    """
    engine = create_engine(sqlalchemy_database_url)
    session_callable = sessionmaker(bind=engine)

    if drop:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)

    return session_callable


get_db = init_db(settings.db.sqlalchemy_url, drop=settings.db.drop)


def get_or_create_user(db: Session, chat_id: int):
    user = db.scalar(select(User).filter_by(chat_id=chat_id))

    if not user:
        user = User(chat_id=chat_id)
        db.add(user)

        book_filter = [1]
        chat_settings = ChatSettings(user=user, book_filter=book_filter)
        db.add(chat_settings)

        db.commit()
        db.refresh(user)

    return user


def get_chat_settings(db: Session, chat_id: int):
    return db.scalar(select(ChatSettings).filter_by(user=get_or_create_user(db, chat_id)))


def update_chat_settings(db: Session, chat_settings_id: int, book_filter: Sequence[int]):
    db.execute(update(ChatSettings).filter_by(id=chat_settings_id).values(book_filter=book_filter))
    db.commit()


def chat_settings_add_rulebook(db: Session, chat_id: int, rulebook_id: int):
    chat_settings = get_chat_settings(db, chat_id)
    chat_settings.book_filter.append(rulebook_id)

    update_chat_settings(db, chat_settings.id, chat_settings.book_filter)
    db.refresh(chat_settings)

    return chat_settings


def chat_settings_remove_rulebook(db: Session, chat_id: int, rulebook_id: int):
    chat_settings = get_chat_settings(db, chat_id)
    chat_settings.book_filter.remove(rulebook_id)

    update_chat_settings(db, chat_settings.id, chat_settings.book_filter)
    db.refresh(chat_settings)

    return chat_settings


def create_saved_spell(db: Session, chat_id: int, spell_id: int):
    saved_spell = SavedSpell(user=get_or_create_user(db, chat_id), spell_id=spell_id)
    db.add(saved_spell)
    db.commit()

    return saved_spell


def delete_saved_spell(db: Session, chat_id: int, spell_id: int):
    db.execute(delete(SavedSpell).filter_by(user=get_or_create_user(db, chat_id), spell_id=spell_id))
    db.commit()


def get_saved_spells(db: Session, chat_id: int) -> List[SavedSpell]:
    return list(db.scalars(select(SavedSpell).filter_by(user=get_or_create_user(db, chat_id))))


def get_saved_spell_by_index(db: Session, chat_id: int, index: int) -> [SavedSpell, int]:
    saved_spells = get_saved_spells(db, chat_id)

    saved_spell = saved_spells[index]
    index_max = len(saved_spells)

    return saved_spell, index_max
