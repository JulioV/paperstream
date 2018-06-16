"""
Create diaries in A5 and A4 sizes based on PDF templates.

Julio Vega
"""
import datetime
import math
import sys
from io import BytesIO
from pathlib import Path

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen import canvas


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)
    return base_path / Path(relative_path)

CORNER_DIR = resource_path("input/1_diaries_to_create/resources")
LOGO_PATH = resource_path(CORNER_DIR / Path("logo.png"))
DEFAULT_FONT = resource_path(CORNER_DIR / Path('FreeSansLocal.ttf'))
CREATED_DIARIES_DIR = resource_path("output/created_diaries/")

#############################################################
#############################################################
#############################################################
##### Algorithm to convert A4 pages into an A5 booklet ######
#############################################################
#############################################################
#############################################################
## Adapted from the work by Luke Plant, https://bitbucket.org/spookylukey/booklet-maker/src

class Sheet(object):
    '''A4 Sheets'''
    def __init__(self):
        self.front = PrintPage()
        self.back = PrintPage()


class PrintPage(object):
    '''A4 page with containers for A4 pages'''
    def __init__(self):
        self.left = PageContainer()
        self.right = PageContainer()


class PageContainer(object):
    '''A5 containers'''
    def __init__(self):
        self.page = None


def build_booklet(pages):
    ''' Build booklet '''
    # Double sized page, with double-sided printing, fits 4 of the original.
    sheet_count = int(math.ceil(len(pages) / 4.0))

    booklet = [Sheet() for i in range(0, sheet_count)]

    # Assign input pages to sheets

    # This is the core algo. To understand it:
    # * pick up 3 A4 sheets, landscape
    # * number the sheets from 1 to 3, starting with bottom one
    # * fold the stack in the middle to form an A5 booklet
    # * work out what order you need to use the front left,
    #   front right, back left and back right sides.

    def containers():
        '''Yields parts of the booklet in the order they should be used.'''
        for sheet in booklet:
            yield sheet.back.right
            yield sheet.front.left

        for sheet in reversed(booklet):
            yield sheet.front.right
            yield sheet.back.left

    for container, page in zip(containers(), pages):
        container.page = page

    return booklet


def add_double_page(writer, page_size, print_page):
    ''' Adds a double page '''
    width, height = page_size
    page = writer.insertBlankPage(width=width, height=height, index=writer.getNumPages())

    # Merge the left page
    l_page = print_page.left.page
    if l_page is not None:
        page.mergePage(l_page)

    # Merge the right page with translation
    r_page = print_page.right.page
    if r_page is not None:
        page.mergeTranslatedPage(r_page, width / 2, 0)


def convert_to_a5_booklet(input_file, blanks=0):
    '''Converts a PDF into a double sided A5 file to print as an A4 (two A5 pages per A4 page)'''

    # Create internal dir to save the a5 files    
    a5_booklets_dir = CREATED_DIARIES_DIR
    Path.mkdir(a5_booklets_dir, parents=True, exist_ok=True)

    # Create the a5 booklet's name
    a5_booklet_name = Path(input_file).stem + "_as_a5_booklet"
    a5_booklet = a5_booklets_dir / Path("{}.pdf".format(a5_booklet_name))

    reader = PdfFileReader(open(input_file, "rb"))
    pages = [reader.getPage(p) for p in range(0, reader.getNumPages())]
    for index in range(0, blanks):
        pages.insert(0, None)

    sheets = build_booklet(pages)

    writer = PdfFileWriter()
    firs_page = reader.getPage(0)
    input_width = firs_page.mediaBox.getWidth()
    output_width = input_width * 2
    input_height = firs_page.mediaBox.getHeight()
    output_height = input_height

    page_size = (output_width, output_height)

    # We want to group fronts and backs together.
    for sheet in sheets:
        add_double_page(writer, page_size, sheet.back)
        add_double_page(writer, page_size, sheet.front)

    with open(a5_booklet, "wb") as a5_booklet_stream:
        writer.write(a5_booklet_stream)
    return a5_booklet

#############################################################
#############################################################
#############################################################
########## Create A4 paper diary ############
#############################################################
#############################################################
#############################################################

def create_diary_cover(participant_id, email, font):
    '''Create cover of the A5 diary'''

    packet = BytesIO()
    cover_canvas = canvas.Canvas(packet, pagesize=A4)
    width, height = A4

    # Centering the logo or participant ID
    if Path.exists(LOGO_PATH):
        logo = ImageReader(LOGO_PATH)
        cover_canvas.drawImage(logo, x=(width * (1/6.0)),
                               y=(height/4),
                               width=width * (4/6.0),
                               preserveAspectRatio=True,
                               mask='auto')
    else:
        cover_canvas.setFont(font, 50)
        cover_canvas.drawCentredString(width/2, height/2, participant_id)

    # Lost legend
    if not (email is None or email == ""):
        cover_canvas.setFont(font, 15)
        cover_canvas.drawCentredString(width/2, 50,
                                "If you find this diary, please email " + email)

    cover_canvas.save()
    packet.seek(0)
    return PdfFileReader(packet).getPage(0)

def create_diary_page(pdf_template, font, top_left_text, page_number, top_right_text):
    packet = BytesIO()
    diary_canvas = canvas.Canvas(packet, pagesize=A5)

    # Header
    diary_canvas.setFont(font, 11)
    diary_canvas.drawRightString(378, 562, str(top_right_text))
    diary_canvas.drawString(36.5, 562, top_left_text)

    # Corners
    corners = [(CORNER_DIR / Path("corner_ul.png"), 25, 553),
                (CORNER_DIR / Path("corner_ur.png"), 365, 553),
                (CORNER_DIR / Path("corner_bl.png"), 25, 15),
                (CORNER_DIR / Path("corner_br.png"), 365, 15)]
    for corner_path, x, y in corners:
        if corner_path.exists():
            corner = ImageReader(corner_path)
            diary_canvas.drawImage(corner, x=x, y=y, mask='auto')

    # Footer
    diary_canvas.setFont(font, 8)
    diary_canvas.drawString(36.5, 24, str(page_number))
    diary_canvas.save()

    # Merge template and additions (header, corners and footer)
    packet.seek(0)
    page_additions = PdfFileReader(packet).getPage(0)

    new_page = PdfFileReader(open(pdf_template, "rb")).getPage(0)
    new_page.mergePage(page_additions)
    new_page.scaleTo(A4[0], A4[1])

    return new_page

def create_a4_diary(pdf_template, pages, top_left_text, email=None, font='Arial'):
    """Creates an A4 diary with [PAGES] from [STARTING_DATE]"""

    starting_date = parse_date(top_left_text)
    font = set_active_font(font)

    # Create output folder/file
    if not Path(pdf_template).exists():
        raise ValueError("Template does not exist {}".format(pdf_template))

    Path.mkdir(CREATED_DIARIES_DIR, parents=True, exist_ok=True)
    a4_document_name = Path(pdf_template).stem
    a4_document_path = CREATED_DIARIES_DIR / Path("{}_diary.pdf".format(a4_document_name))

    pdf_file = PdfFileWriter()

    # Cover
    pdf_file.addPage(create_diary_cover(a4_document_name, email, font))
    pdf_file.addBlankPage()

    # Pages
    for page in range(1, pages+1):
        if starting_date is not None:
            top_left_text = starting_date.strftime('%A, %d %b %Y')
            starting_date += datetime.timedelta(days=1)
        new_page = create_diary_page(pdf_template, font, top_left_text,page, a4_document_name)
        pdf_file.addPage(new_page)

    # Backcover
    pdf_file.addBlankPage()

    # Save a4 document
    with open(a4_document_path, "wb") as output_stream:
        pdf_file.write(output_stream)

    return a4_document_path

def set_active_font(font):
    """Register the font to use in header and footer of the diary"""
    try:
        pdfmetrics.registerFont(TTFont(font, font + '.ttf'))
    except TTFError:
        font = 'FreeSansLocal'        
        pdfmetrics.registerFont(TTFont(font, DEFAULT_FONT))
    return font

def parse_date(s):
    try:
        return datetime.datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        return None