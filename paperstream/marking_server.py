# things.py

# Let's get this party started!
import os
import falcon
import json
import paperstream.encode_diary as encode
import paperstream.create_diary as create
import cv2
import traceback
import zipfile
import sys

from paperstream.static_resources_middleware import StaticResourcesMiddleware
from falcon_multipart.middleware import MultipartMiddleware

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# These paths are for the web interface, don't call resource_path
WEB_ANSWER_AREA_PATH = resource_path("static/template.png")
DOWNLOADS_DIR = r"static/downloads"


class TemplateResource(object):
    def on_get(self, req, resp):
        """Checks whether or not an empty diary page exists for encoding"""
        resp.set_header('Content-Type', 'text/json')

        success, code = TemplateResource.extract_template_answer_area()
        if success:
            resp.body = json.dumps({"template": os.path.basename(code)})
        else:
            if code == 'saved':
                raise falcon.HTTPInternalServerError(title="There was a problem processing the encoding template",
                                                     description="Please contact the development team.")
            elif code == 'encoding':
                raise falcon.HTTPInternalServerError(title="Encoding error in template file",
                                                     description="The pages of the tiff file {} were encoded using an old jpeg format. This is usually caused by the scanner machine that has been used to create this file. \nUse the 'IrfanView' app or Photoshop to change the compresion of the file to None or LSW. See the docs for more help.".format(template_path))
            elif code == 'empty':
                resp.body = json.dumps({"template": ""})

    def extract_template_answer_area():
        """ Extracts the answer area from a TIF or PNG file """
        tif_files = encode.get_files_in_directory(encode.TEMPLATE_DIR, ".tif")
        png_files = encode.get_files_in_directory(encode.TEMPLATE_DIR, ".png")
        files = tif_files + png_files

        # If there is at least one tif or png file in the template dir
        if files:
            template_path = files[0]
            try:
                template_answer_area = encode.get_first_page_answer_area(template_path)
                image_saved = cv2.imwrite(WEB_ANSWER_AREA_PATH, template_answer_area)
                if not image_saved:
                    return (False, "saving")
                else:
                    return (True, template_path)
            except OSError:
                return (False, "encoding")
        else:
            return (False, "empty")


class ScannedDiariesResource(object):
    def on_get(self, req, resp):
        """Returns a list of all of the tif files (diaries) present in DIARIES_TO_ENCODE_DIR"""
        resp.set_header('Content-Type', 'text/json')
        tif_paths = encode.get_files_in_directory(encode.DIARIES_TO_ENCODE_DIR, ".tif")
        zip_paths = encode.get_files_in_directory(encode.DIARIES_TO_ENCODE_DIR, ".zip")
        diaries_paths = tif_paths + zip_paths
        def extract_file_name(path): return os.path.basename(path)
        resp.body = json.dumps({"diaries": list(map(extract_file_name, diaries_paths)),
                                "diaries_paths": diaries_paths})


class PDFTemplateDiariesResource(object):
    def on_get(self, req, resp):
        """Returns a list of all of the PDF files (templates) present in DIARIES_TO_CREATE_DIR"""
        resp.set_header('Content-Type', 'text/json')
        diaries_paths = encode.get_files_in_directory(encode.DIARIES_TO_CREATE_DIR, ".pdf")

        def extract_file_name(path): return os.path.basename(path)
        resp.body = json.dumps({"templates_file_names": list(map(extract_file_name, diaries_paths)),
                                "templates_paths": diaries_paths})


class EncodeResource(object):
    def on_post(self, req, resp):
        """
        Encodes a diary (tif or zip file) based on a rubric (created in the web interface) and a blank 
        page of the diary (tif or zip file) present in TEMPLATE_DIR
        """
        resp.set_header('Content-Type', 'text/json')
        raw_json = req.stream.read().decode('utf-8')
        content = json.loads(raw_json, encoding='utf-8')

        try:
            rubric = content.get("rubric")
            diary_path = content.get("diary")
            date = content.get("date")
            date = encode.valid_date(date)

            encoded_diary = encode.encode_diary(diary_path, rubric, date)
            resp.body = json.dumps(encoded_diary)

            print("Diary Encoded: " + json.dumps(encoded_diary))
        except Exception as e:
            print(str(type(e)))
            print(str(e))
            print(traceback.print_tb(e.__traceback__))
            raise falcon.HTTPInternalServerError(title="Error encoding diary: " + str(type(e)),
                                                 description=(str(e) +
                                                              ','.join(traceback.format_tb(e.__traceback__))))


class CreateResource(object):
    def on_post(self, req, resp):
        """Creates a diary based on a PDF template"""
        resp.set_header('Content-Type', 'text/json')

        raw_json = req.stream.read().decode('utf-8')
        content = json.loads(raw_json, encoding='utf-8')

        try:
            # Parse parameters
            pdf_template = content.get("pdf_template")
            pages = int(content.get("pages"))
            starting_date = content.get("date")
            email = content.get("email")
            font = content.get("font")

            a4_diary = create.create_a4_diary(pdf_template,
                                                 pages,
                                                 starting_date,
                                                 email=email,
                                                 font=font)

            a5_booklet = create.convert_to_a5_booklet(a4_diary)
            resp.body = json.dumps([str(a4_diary), str(a5_booklet)])

        except Exception as e:
            print(str(type(e)))
            print(str(e))
            print(traceback.print_tb(e.__traceback__))
            raise falcon.HTTPInternalServerError(title="Error creating diary: " + str(type(e)),
                                                 description=(str(e) +
                                                              ','.join(traceback.format_tb(e.__traceback__))))


class DownloadFilesResource(object):
    def compress_files(files, zip_name):
        "Compress [files] into a zip file named [zip_name]"

        if files and len(files) > 0:
            zip_path = os.path.join(DOWNLOADS_DIR, zip_name)
            authorised_folders = ["encoded_diaries", "created_diaries"]
            with zipfile.ZipFile(resource_path(zip_path), 'w') as myzip:

                if isinstance(files[0], list):
                    for a4_document, a5_document in files:
                        base_folder_a4 = os.path.basename(os.path.dirname(a4_document))
                        base_folder_a5 = os.path.basename(os.path.dirname(a5_document))
                        if base_folder_a4 in authorised_folders:
                            myzip.write(a4_document, "a4_diaries/" + (os.path.basename(a4_document)))
                        if base_folder_a5 in authorised_folders:
                            myzip.write(a5_document, "a5_diaries(to print on A4 paper)/" + (os.path.basename(a5_document)))
                
                elif isinstance(files[0], str):
                    for answers_file in files:
                        base_folder = os.path.basename(os.path.dirname(answers_file))
                        if base_folder in authorised_folders:
                            myzip.write(answers_file, (os.path.basename(answers_file)))
                
            return zip_path
        else:
            raise Exception("There are no diaries to encode")

    def on_post(self, req, resp):
        """Handles the compression of files into a zip file"""
        resp.set_header('Content-Type', 'text/json')
        raw_json = req.stream.read().decode('utf-8')
        content = json.loads(raw_json, encoding='utf-8')

        try:
            files = content.get("files")
            zip_name = content.get("name")
            zip_file = DownloadFilesResource.compress_files(files, zip_name)
            resp.body = json.dumps({'file': zip_file})
            print("Zip created")
        except Exception as e:
            print(str(type(e)))
            print(str(e))
            print(traceback.print_tb(e.__traceback__))

            raise falcon.HTTPInternalServerError(title="Error downloading files: " + str(type(e)),
                                                 description=(str(e) +
                                                              ','.join(traceback.format_tb(e.__traceback__))))


class UploadFilesResource(object):
    def on_post(self, req, resp):
        file = req.get_param('file')
        folder = req.get_param('folder')
        if folder == "creation":
            filename = file.filename
            with(open(os.path.join(encode.DIARIES_TO_CREATE_DIR, filename), 'wb')) as writer:
                writer.write(file.file.read())
        elif folder == "encodingTemplate":
            filename = file.filename
            with(open(os.path.join(encode.TEMPLATE_DIR, filename), 'wb')) as writer:
                writer.write(file.file.read())
            # UploadFilesResource.reload_template()
        elif folder == "encodingDiaries":
            filename = file.filename
            with(open(os.path.join(encode.DIARIES_TO_ENCODE_DIR, filename), 'wb')) as writer:
                writer.write(file.file.read())
    def reload_template():
        success, code = TemplateResource.extract_template_answer_area()
        # TODO feedback this errors to GUI
        return success


class DeleteFilesResource(object):
    def delete_all_files_in_dir(extension, dir_path):
        filenames = os.listdir(dir_path)
        for filename in filenames:
            if filename.endswith(extension):
                os.remove(os.path.join(dir_path, filename))

    def on_post(self, req, resp):
        resp.set_header('Content-Type', 'text/json')
        raw_json = req.stream.read().decode('utf-8')
        content = json.loads(raw_json, encoding='utf-8')

        folder = content.get("folder")
        if folder == "creation":
            DeleteFilesResource.delete_all_files_in_dir(".pdf", encode.DIARIES_TO_CREATE_DIR)
        elif folder == "encodingTemplate":
            DeleteFilesResource.delete_all_files_in_dir(".tif", encode.TEMPLATE_DIR)
            DeleteFilesResource.delete_all_files_in_dir(".png", encode.TEMPLATE_DIR)
        elif folder == "encodingDiaries":
            DeleteFilesResource.delete_all_files_in_dir(".tif", encode.DIARIES_TO_ENCODE_DIR)
            DeleteFilesResource.delete_all_files_in_dir(".zip", encode.DIARIES_TO_ENCODE_DIR)

        resp.body = json.dumps({"response": "ok"})


def my_serializer(req, resp, exception):
    representation = None

    preferred = req.client_prefers(('application/x-yaml',
                                    'application/json'))

    if preferred is not None:
        if preferred == 'application/json':
            representation = exception.to_json()

        resp.body = representation
        resp.content_type = preferred

    resp.append_header('Vary', 'Accept')


# Configure Falcon
app = falcon.API(middleware=[MultipartMiddleware()])

# Add static routing
app.add_sink(StaticResourcesMiddleware("static", resource_path("./static")), "")

app.set_error_serializer(my_serializer)


app.add_route('/encoding_template', TemplateResource())
app.add_route('/scanned_diaries', ScannedDiariesResource())
app.add_route('/pdf_template_diaries', PDFTemplateDiariesResource())
app.add_route('/encode_diary', EncodeResource())
app.add_route('/create_diary', CreateResource())
app.add_route('/download_files', DownloadFilesResource())
app.add_route('/upload_files', UploadFilesResource())
app.add_route('/delete_files', DeleteFilesResource())
