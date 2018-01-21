"""
Create diaries in A5 and A4 sizes based on PDF templates.

Julio Vega
"""
from PyPDF2 import PdfFileWriter, PdfFileReader
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.ttfonts import TTFError
from reportlab.lib.utils import ImageReader
# Barcode
# from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# Others
import datetime
import argparse
import math
import glob
import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

INPUT_DIR = resource_path("input/1_diaries_to_create/")
CORNER_DIR = resource_path(os.path.join(INPUT_DIR, "resources"))
LOGO_PATH = resource_path(os.path.join(CORNER_DIR, "logo.png"))

CREATED_DIARIES_DIR = resource_path("output/created_diaries/")

class DiaryException(Exception):
    '''Base clase for exceptions related to this script'''

class MissingFolder(DiaryException):
    '''Raised when a folder is missing'''

#############################################################
#############################################################
#############################################################
##### Algorithm to convert A5 pages into an A4 booklet #####
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


def convert_a5_in_a4_booklet(input_name, output_name, blanks=0):
    '''Converts an A5 input PDF into a double sided A4 file ready to print'''
    reader = PdfFileReader(open(input_name, "rb"))
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

    writer.write(open(output_name, "wb"))

#############################################################
#############################################################
#############################################################
########## Algorithm to create an A5 paper diary ############
#############################################################
#############################################################
#############################################################

def create_diary_cover(participant_id, email, font):
    '''Create cover of the A5 diary'''

    packet = BytesIO()
    cover_canvas = canvas.Canvas(packet, pagesize=A5)
    width, height = A5

    # Centering the logo or participant ID
    logo_path = LOGO_PATH
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_width, logo_height = logo.getSize()
        image_scale_width = 250
        aspect = logo_height / float(logo_width)
        image_scale_height = (image_scale_width * aspect)
        cover_canvas.drawImage(logo, x=(width/2) - (image_scale_width/2),
                               y=(height/4)-(image_scale_height/2),
                               width=image_scale_width, preserveAspectRatio=True, mask='auto')
    else:
        print("No logo.png in input/1_diaries_to_create/resources.")
        print("Using participant ID instead")
        cover_canvas.setFont(font, 50)
        cover_canvas.drawString(width/2 - 60, height/2 + 70, "Diary")
        cover_canvas.drawString(width/2 - 50, height/2, participant_id)

    # Lost legend
    if not (email is None or email == ""):
        cover_canvas.setFont(font, 10)
        cover_canvas.drawString(75, 50,
                                "If you find this diary, please email " + email)

    cover_canvas.save()
    packet.seek(0)
    return PdfFileReader(packet).getPage(0)

def built_a5_diary(a5_path, pdf_template, participant_id, pages, starting_date, email, font):
    """Creates an A5 diary with PAGES from STARTING_DATE"""

    output_a5 = PdfFileWriter()
    print("Processing {}...".format(participant_id))

    # Cover with logo and email if provided
    output_a5.addPage(create_diary_cover(participant_id, email, font))
    output_a5.addBlankPage()

    for page in range(1, pages+1):
        packet = BytesIO()
        diary_canvas = canvas.Canvas(packet, pagesize=A5)

        # Barcode
        # qr_code = qr.QrCodeWidget(starting_date.strftime('%y%m%d') + participant_id)
        # bounds = qr_code.getBounds()
        # width = bounds[2] - bounds[0]
        # height = bounds[3] - bounds[1]
        # qr_draw = Drawing(30, 30, transform=[30./width, 0, 0, 30./height, 0, 0])
        # qr_draw.add(qr_code)
        # renderPDF.draw(qr_draw, diary_canvas, 355, 545)

        # Header
        diary_canvas.setFont(font, 11)
        diary_canvas.drawString(360 - (len(str(participant_id))), 562, str(participant_id).zfill(2))
        diary_canvas.setFont(font, 11)
        diary_canvas.drawString(36.5, 562, starting_date.strftime('%A, %d %b %Y'))

        # Corners
        corners = [(os.path.join(CORNER_DIR, "corner_ul.png"), 25, 553),
                   (os.path.join(CORNER_DIR, "corner_ur.png"), 365, 553),
                   (os.path.join(CORNER_DIR, "corner_bl.png"), 25, 15),
                   (os.path.join(CORNER_DIR, "corner_br.png"), 365, 15)]
        for corner_path, x, y in corners:
            if os.path.exists(corner_path):
                corner = ImageReader(corner_path)
                diary_canvas.drawImage(corner, x=x, y=y, mask='auto')

        # Footer
        diary_canvas.setFont(font, 8)
        diary_canvas.drawString(36.5, 24, str(page))
        diary_canvas.save()

        # Merge template with Barcode, Header and Footer
        packet.seek(0)
        newPage = PdfFileReader(open(pdf_template, "rb")).getPage(0)
        newPage.mergePage(PdfFileReader(packet).getPage(0))
        output_a5.addPage(newPage)

        starting_date += datetime.timedelta(days=1)

    # Backcover
    output_a5.addBlankPage()

    # Save A5 diary
    output_stream = open(a5_path, "wb")
    output_a5.write(output_stream)
    output_stream.close()

    return True

def create_diary(pdf_template, pages, starting_date, email=None, font="Arial"):
    """This method creates a diary based on [pdf_template] with [pages] from [starting_date]"""
    font = set_font(font)

    if not os.path.exists(INPUT_DIR):
        raise MissingFolder("Subfolder 'input' is missing")

    a4_output_dir, a5_output_dir = create_output_folders()
    participant_id = os.path.splitext(os.path.basename(pdf_template))[0]

    a5_path = os.path.join(a5_output_dir, "preliminar_" + participant_id + ".pdf")
    a4_path = os.path.join(a4_output_dir, "diary_" + participant_id + ".pdf")

    built_a5_diary(a5_path, pdf_template, participant_id, pages, starting_date, email, font)
    convert_a5_in_a4_booklet(a5_path, a4_path, 0)
    return a4_path

def create_output_folders():
    """Create output folders for the A4 and A5 versions of the diary"""
    a4_output_dir = CREATED_DIARIES_DIR
    if not os.path.exists(a4_output_dir):
        os.makedirs(a4_output_dir)

    a5_output_dir = os.path.join(a4_output_dir, "a5_references")
    if not os.path.exists(a5_output_dir):
        os.makedirs(a5_output_dir)

    return [a4_output_dir, a5_output_dir]

def try_set_font(font):
    """ Try to set a font, return True if sucess"""
    try:
        pdfmetrics.registerFont(TTFont(font, font + '.ttf'))
        return True
    except TTFError:
        return False


def set_font(font):
    """Select a font to use in the header and footer of the diary"""
    try:
        pdfmetrics.registerFont(TTFont(font, font + '.ttf'))
    except TTFError:
        old_font = font
        if try_set_font("Arial"):
            font = "Arial"
        elif try_set_font("FreeSans"):
            font = "FreeSans"
        print("The font {} does not exist in your system, using {}".format(old_font, font))
    return font

def main(pages, starting_date, email, font):
    font = set_font(font)

    if not os.path.exists(INPUT_DIR):
        raise MissingFolder("Subfolder 'input' is missing")

    a4_output_dir, a5_output_dir = create_output_folders()

    pdf_templates = list(glob.glob(os.path.join(INPUT_DIR, "*.pdf")))
    for pdf_template in pdf_templates:
        create_diary(pdf_template, pages, starting_date, email, font)

def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Create an A5 diary from a PDF template as an A4 booklet ready to print')
    parser.add_argument('pages', type=int, help='number of pages that each diary will have')
    parser.add_argument('starting_date', type=valid_date,
                        help='starting date for the diary (format DD/MM/YYY), '
                        'subsequent pages will increment it by one day each time')
    parser.add_argument('--email', help='email address printed in case the diary is lost')
    parser.add_argument('--font', default='Arial', help='font for header and footer annotations')
    args = parser.parse_args()
    main(args.pages, args.starting_date, args.email, args.font)
 