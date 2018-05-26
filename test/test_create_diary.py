import unittest
from pathlib import Path
import paperstream.create_diary as create
from shutil import copyfile
class TestCreateDiary(unittest.TestCase):

    def setUp(self):
        create.CORNER_DIR = Path("test/input/resources")
        create.DEFAULT_FONT = Path(create.CORNER_DIR / Path('FreeSansLocal.ttf')).absolute()
        create.CREATED_DIARIES_DIR = Path("test/output/")

    def test_create_diary_default_font(self):
        create.LOGO_PATH = create.CORNER_DIR / Path("invalid_path")

        a4_document = create.create_a4_diary("test/input/P01.pdf", 3, "01/01/2018", font="FreeSansLocal")
        test_a4_document = Path("test/comparison_files/a4_default_font.pdf")

        self.assertTrue(a4_document.stat().st_size == test_a4_document.stat().st_size)

    def test_create_diary_default_logo(self):
        create.LOGO_PATH = create.CORNER_DIR / Path("logo.png")

        a4_document = create.create_a4_diary("test/input/P01.pdf", 3, "01/01/2018")
        test_a4_document = Path("test/comparison_files/a4_default_logo.pdf")

        self.assertTrue(a4_document.stat().st_size == test_a4_document.stat().st_size)

    def test_create_diary_default_email(self):
        create.LOGO_PATH = create.CORNER_DIR / Path("invalid_path.png")

        a4_document = create.create_a4_diary("test/input/P01.pdf", 3, "01/01/2018", email="test@test.com")
        test_a4_document = Path("test/comparison_files/a4_default_email.pdf")

        self.assertTrue(a4_document.stat().st_size == test_a4_document.stat().st_size)

    def test_convert_a4_to_a5(self):
        a5_booklet = create.convert_to_a5_booklet("test/comparison_files/a4_default_font.pdf")
        test_a5_booklet = Path("test/comparison_files/a4_default_font_as_a5_booklet.pdf")

        self.assertTrue(a5_booklet.stat().st_size == test_a5_booklet.stat().st_size)


if __name__ == '__main__':
    unittest.main()