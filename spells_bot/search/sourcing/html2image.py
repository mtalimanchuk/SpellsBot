from pathlib import Path
from typing import Union

import requests

from spells_bot.config import HctiSettings
from spells_bot.utils.log import create_logger
from spells_bot.search.sourcing.datatypes import SpellTable


logger = create_logger("hcti")


class HctiApi:
    def __init__(self, settings: HctiSettings):
        self._settings = settings
        self.css = self._load_css(settings.css_file)

    @staticmethod
    def _load_css(path):
        with open(path, "r", encoding="utf-8") as css_f:
            css = css_f.read()
        return css

    def create_image(self, html: str):
        """Create image via hcti api from html and pre-configured css

        :param html: raw html
        :return:
        """
        data = {
            "html": html,
            "css": self.css,
            "device_scale": 1,
        }
        response = requests.post(
            url=self._settings.url,
            data=data,
            auth=(self._settings.user_id, self._settings.api_key),
        )

        image_url = None
        try:
            image_url = response.json()["url"]
        except KeyError:
            logger.error(str(response.json()))

        return image_url

    @staticmethod
    def download_image(
        url: str, download_path: Union[Path, str], overwrite: bool = False
    ) -> None:
        """Download image

        :param url: image url
        :param download_path: path to file
        :param overwrite: overwrite existing file if True
        :return:
        """
        download_path = Path(download_path)
        if overwrite or not download_path.exists():
            try:
                download_path.parent.mkdir(exist_ok=True, parents=True)
                response = requests.get(url)
                with open(download_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Downloaded {url} to {download_path}")
            except Exception as e:
                logger.error(f"Failed to save {url} to {download_path} because {e}")

    def find_or_create(self, html: str, path: Union[Path, str, None]):
        """Discover image locally or create and download

        :param html: raw html
        :param path: possible image path
        :return:
        """
        url = None
        path = Path(path)

        if not path.is_file():
            url = self.create_image(html)
            self.download_image(url, path)

        return SpellTable(html=html, url=url, path=path)
