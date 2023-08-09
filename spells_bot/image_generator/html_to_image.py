from os import getcwd
from pathlib import Path
from typing import Union, List, Sequence, Tuple

from html2image import Html2Image


class HtmlToImage:
    def __init__(self, data_root_dir: Union[Path, str], css_file: Union[Path, str]):
        self.data_root_dir = Path(data_root_dir)
        self.css_file = Path(css_file)
        with self.css_file.open("r") as css_f:
            self.css_str = css_f.read()

        self.hti = Html2Image(
            custom_flags=[
                "--no-sandbox",
                "--headless",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage",
                "--remote-allow-origins=*",
                "--hide-scrollbars",
            ],
            temp_path=f"{getcwd()}/.tmp",
            output_path=data_root_dir,
        )

    def _class_table_dir(self, class_alias: str):
        class_dir = self.data_root_dir / "class_tables" / class_alias
        class_dir.mkdir(parents=True, exist_ok=True)
        return class_dir

    def _spell_table_dir(self, spell_alias: str):
        class_dir = self.data_root_dir / "spell_tables" / spell_alias
        class_dir.mkdir(parents=True, exist_ok=True)
        return class_dir

    def _load_or_create_screenshots(
        self, html_strs: Sequence[str], size: Tuple[int, int] = None, force_create: bool = False
    ):
        if not size:
            size = (1920, 1080)

        result_paths = []

        for idx, html_str in enumerate(html_strs):
            filename = f"{idx}.jpg"
            file_path = Path(self.hti.output_path) / filename
            if force_create or not file_path.exists():
                self.hti.screenshot(html_str=html_str, css_str=self.css_str, save_as=filename, size=size)
            result_paths.append(file_path)

        return result_paths

    def class_tables(self, html_strs: List[str], class_alias: str):
        self.hti.output_path = self._class_table_dir(class_alias)
        return self._load_or_create_screenshots(html_strs)

    def spell_tables(self, html_strs: List[str], spell_alias: str):
        self.hti.output_path = self._spell_table_dir(spell_alias)
        return self._load_or_create_screenshots(html_strs)
