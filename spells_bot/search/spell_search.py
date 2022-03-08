import math

from spells_bot.config import (
    DatabaseSettings,
    DataSourceSettings,
    StorageSettings,
    HctiSettings,
)
from spells_bot.search.sourcing import Database, SourceUpdater, HctiApi
from spells_bot.utils.log import create_logger

logger = create_logger("search")


class SpellSearch:
    def __init__(
        self,
        db_settings: DatabaseSettings,
        storage_settings: StorageSettings,
        source_settings: DataSourceSettings,
        hcti_settings: HctiSettings,
    ) -> None:
        self._db_name = db_settings.sqlalchemy_url
        self.db = Database(db_settings)

        self.data_root_dir = storage_settings.data_root_dir
        self.classinfo_tables_dir = storage_settings.data_root_dir / "classinfo"
        self.spell_tables_dir = storage_settings.data_root_dir / "tables"

        self.source = SourceUpdater(source_settings)
        self.hcti = HctiApi(hcti_settings)
        self._check_db_readiness()

    def _check_db_readiness(self):
        if not self.db.has_spell_list():
            logger.info(f"{self._db_name} is not prepared, updating spell list...")
            self.update_sources()

        logger.info(f"{self._db_name} is ready")

    def get_chat_settings(self, chat_id: int):
        return self.db.get_or_create_chat_settings(chat_id)

    def update_chat_settings(self, chat_id: int, book: str):
        return self.db.update_book_filter(chat_id, book)

    def update_sources(self):
        spells, classes, schools = self.source.update_registry()
        self.db.create_or_update_registry(spells, classes, schools)

    def short_info(self, query: str, chat_id: int, top_n: int = 10):
        return list(self.db.iter_short_spell_info_by_name(query, chat_id))[:top_n]

    def extended_info(self, spell_alias: str):
        _, extended_spell_info = self.full_info(spell_alias)
        return extended_spell_info

    def full_info(self, spell_alias: str):
        short_spell_info, extended_spell_info = self.db.get_full_spell_info(spell_alias)

        if not extended_spell_info:
            extended_spell_info = self.source.update_spell_info(spell_alias)

            updated_tables = []
            for t_idx, t in enumerate(extended_spell_info.tables):
                table_image_path = self.spell_tables_dir / spell_alias / f"{t_idx}.png"
                table = self.hcti.find_or_create(t.html, table_image_path)
                updated_tables.append(table)

            extended_spell_info = self.db.create_extended_spell_info(
                spell_alias, extended_spell_info, updated_tables
            )

        return short_spell_info, extended_spell_info

    def class_info(self, class_id: int):
        return self.db.get_class(class_id)

    def iter_classes(self, chat_id: int):
        yield from self.db.iter_classes(chat_id)

    def iter_class_info_tables(self, class_id: int):
        class_info = self.class_info(class_id)
        class_info_dir = self.classinfo_tables_dir / class_info.alias

        for p in class_info_dir.glob("*.png"):
            yield p, class_info

    def iter_levels(self, class_id: int):
        yield from self.db.iter_levels(class_id)

    def paginate_short_info_by_level(
        self,
        class_id: int,
        level: int,
        chat_id: int,
        page: int = 0,
        n_per_page: int = 50,
    ):
        all_spells = list(
            self.db.iter_short_spell_info_by_class_level(class_id, level, chat_id)
        )
        n_pages_total = math.ceil(len(all_spells) / n_per_page)
        return n_pages_total, all_spells[n_per_page * page : n_per_page * (page + 1)]
        # results_df = self.spells_df.loc[
        #     self.spells_df["Круг"].str.contains(class_and_level),
        #     ["name", "sup", "short_desc", "school"],
        # ]
        #
        # for school, row in results_df.groupby("school"):
        #     yield school, row.to_dict("records")
