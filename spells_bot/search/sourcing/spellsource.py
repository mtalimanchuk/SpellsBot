import json
import re
from typing import List, Tuple

from bs4 import BeautifulSoup
from requests_html import HTMLSession

from spells_bot.config import DataSourceSettings
from spells_bot.search.sourcing.datatypes import (
    ExtendedSpellInfo,
    ClassInfo,
    SchoolInfo,
    ShortSpellInfo,
    ClassInfoSpellRestriction,
    SpellTable,
)
from spells_bot.utils.log import create_logger


logger = create_logger("source_updater")

CLASSES_KEY_MAP = {
    "Id": "id",
    "Name": "name",
    "IsOwnSpellList": "is_own_spell_list",
    "MaxSpellLvl": "max_spell_lvl",
    "ParentClassIds": "parent_class_ids",
}

SCHOOLS_KEY_MAP = {
    "Id": "id",
    "Name": "name",
    "TypeId": "type_id",
    "TypeName": "type_name",
}

SPELLS_KEY_MAP = {
    "Alias": "alias",
    "ShortDescriptionComponents": "short_description_components",
    "BookAbbreviation": "book_abbreviation",
    "BookAlias": "book_alias",
    "ShortDescription": "short_description",
    "SchoolIds": "schools",
    "ClassSpell": "classes",
    "Name": "name",
    "IsRaceSpell": "is_race_spell",
}


def _rename_keys(original_dict, key_map):
    return {key_map[k]: v for k, v in original_dict.items()}


class SourceUpdater:
    def __init__(self, settings: DataSourceSettings, save_dir: str = None):
        self._settings = settings
        self.spell_list_url = settings.spell_list_url.rstrip("/")
        self.class_list_url = settings.class_list_url.rstrip("/")
        self.prestige_class_list_url = settings.prestige_class_list_url.rstrip("/")
        self.spell_info_url_prefix = settings.spell_info_url_prefix.rstrip("/")
        self.save_dir = save_dir

    @staticmethod
    def _extract_data_from_js(
        raw_data: str,
        data_type: str,
        variable_prefix: str = None,
        variable_postfix: str = None,
    ) -> List[dict]:
        """Strip syntax and extra characters and load data as json

        :param raw_data: string with js var containing data inside its value
        :param data_type: "spells", "classes" or "schools"
        :param variable_prefix: (optional) string before data value, defaults to "var {data_type} = \\'"
        :param variable_postfix: (optional) string after data value, defaults to "\\';&#13;"
        :return: list of dicts with data
        """
        variable_prefix = variable_prefix or f"var {data_type} = \\'"
        variable_postfix = variable_postfix or "\\';&#13;"
        start, end = len(variable_prefix) - 1, -(len(variable_postfix) - 1)

        raw_json = raw_data.strip()[start:end]
        json_data = json.loads(raw_json)

        return json_data

    @staticmethod
    def _iter_class_extra_info(raw_data):
        for p in raw_data.find("p.indent"):
            try:
                header = p.find("span.textHeader")[0]
                name_html = header.find("a")[0]
                alias = list(name_html.links)[0].split("/")[-1]
                name = name_html.text

                sup_html = header.find("sup")[0]
                book_alias = list(sup_html.links)[0].split("/")[-1]
                book_abbreviation = sup_html.text

                short_description = p.text.split(":")[-1]

                extra_class_info = {
                    "alias": alias,
                    "name": name,
                    "book_alias": book_alias,
                    "book_abbreviation": book_abbreviation,
                    "short_description": short_description,
                }

                yield name, extra_class_info
            except IndexError:
                pass

    def _extract_classes_from_js_and_extra_data(
        self,
        raw_classes_data: str,
        raw_basic_class_extra_data,
        raw_prestige_class_extra_data,
    ) -> List[ClassInfo]:
        classes = []

        extra_basic_class_data = list(
            self._iter_class_extra_info(raw_basic_class_extra_data)
        )
        extra_prestige_class_data = list(
            self._iter_class_extra_info(raw_prestige_class_extra_data)
        )
        extra_class_data_map = {
            name: data
            for name, data in extra_basic_class_data + extra_prestige_class_data
        }

        for class_info in self._extract_data_from_js(raw_classes_data, "classes"):
            class_info_kwargs = _rename_keys(class_info, CLASSES_KEY_MAP)
            class_name = class_info_kwargs["name"]

            extra_class_info_kwargs = extra_class_data_map.get(class_name, {})
            class_info_kwargs.update(extra_class_info_kwargs)

            classes.append(ClassInfo(**class_info_kwargs))

        return classes

    def _extract_schools_from_js(self, raw_schools_data: str) -> List[SchoolInfo]:
        schools = []

        for school_info in self._extract_data_from_js(raw_schools_data, "schools"):
            school_info_kwargs = _rename_keys(school_info, SCHOOLS_KEY_MAP)
            schools.append(SchoolInfo(**school_info_kwargs))

        return schools

    def _extract_spells_from_js(
        self, raw_spell_data: str, classes: List[ClassInfo], schools: List[SchoolInfo]
    ) -> List[ShortSpellInfo]:
        spells = []

        id2class = {c.id: c for c in classes}
        id2school = {s.id: s for s in schools}

        for spell in self._extract_data_from_js(raw_spell_data, "spells"):
            class_restrictions = []
            for restriction in spell["ClassSpell"]:
                class_info = id2class[restriction["ClassId"]]
                class_info_restriction = ClassInfoSpellRestriction(
                    **class_info.dict(), level=restriction["Level"]
                )
                class_restrictions.append(class_info_restriction)

            spell["ClassSpell"] = class_restrictions
            spell["SchoolIds"] = [id2school[idx] for idx in spell["SchoolIds"]]
            # try:
            spell["ShortDescription"] = re.sub(
                "<a href.*?>|</a>", "", spell["ShortDescription"]
            )
            # except ParserError

            spell_kwargs = _rename_keys(spell, SPELLS_KEY_MAP)
            spells.append(ShortSpellInfo(**spell_kwargs))

        return spells

    def _collect_spell_list_js_lines(self) -> Tuple[str, str, str]:
        """Scrape raw js strings containing spells, classes, schools data

        :return:
        """
        with HTMLSession() as sess:
            response = sess.get(self.spell_list_url)

        script_with_data = response.html.find("script")[1].full_text
        spells_raw, classes_raw, schools_raw = script_with_data.split("\n")[1:4]

        return spells_raw, classes_raw, schools_raw

    def _collect_extra_class_data(self):
        with HTMLSession() as sess:
            basic_classes_response = sess.get(self._settings.class_list_url)
            prestige_classes_response = sess.get(self._settings.prestige_class_list_url)

        return basic_classes_response.html, prestige_classes_response.html

    def _collect_spell_info(self, spell_alias: str) -> ExtendedSpellInfo:
        """Scrape extended spell info

        :param spell_alias: camelCase spell name
        :return:
        """
        with HTMLSession() as sess:
            response = sess.get(f"{self.spell_info_url_prefix}/{spell_alias}")

        # using lxml soup to correctly parse tables, because they're mangled with <p> tags
        soup = BeautifulSoup(response.html.html, "lxml")

        full_name_raw = soup.find("h1", class_="detailPage").text
        full_name = full_name_raw.strip().split("\n")[0]
        school = None
        variables = {}
        text_lines = []
        tables = []

        for table in soup.find_all("table"):
            table = re.sub('<p class="indent">|</p>', "", str(table))
            tables.append(SpellTable(html=table))

        for p in response.html.find("p.indent"):
            var_header = p.find("span.textHeader")
            table_row = p.find("table, thead, tbody, tr, td")

            if p.text.startswith("Школа"):
                school = p.text
            elif var_header:
                full_text_raw = p.full_text
                var_name_raw = var_header[0].text
                var_value_raw = full_text_raw[len(var_name_raw) :]

                var_name, var_value = var_name_raw.strip(" :"), var_value_raw.strip()
                variables[var_name] = var_value
            elif table_row:
                pass
            else:
                if p.text:
                    text_lines.append(p.text)

        return ExtendedSpellInfo(
            full_name=full_name,
            school=school,
            variables=variables,
            text="\n".join(text_lines),
            tables=tables,
        )

    def update_spell_info(self, spell_alias: str) -> ExtendedSpellInfo:
        """Get spell info

        :param spell_alias:
        :return:
        """
        extended_spell_info = self._collect_spell_info(spell_alias)

        logger.info(f"Collected extended spell info for {spell_alias}")
        return extended_spell_info

    def update_registry(self):
        """Get spells, classes, schools data

        :return:
        """
        spells_raw, classes_raw, schools_raw = self._collect_spell_list_js_lines()
        (
            basic_classes_extra_raw,
            prestige_classes_extra_raw,
        ) = self._collect_extra_class_data()

        schools = self._extract_schools_from_js(schools_raw)
        classes = self._extract_classes_from_js_and_extra_data(
            classes_raw, basic_classes_extra_raw, prestige_classes_extra_raw
        )
        spells = self._extract_spells_from_js(spells_raw, classes, schools)

        logger.info(
            f"Collected registry, found: {len(spells)} spells, {len(classes)} classes, {len(schools)} schools"
        )
        return spells, classes, schools
