"""
Encode a diary. The diary must be scanned into a tiff/png file. The rubric to encode it must be
created through the web interface.

Julio Vega
"""
import os
import cv2
import datetime
import json
import numpy as np
import PyPDF2
import csv
import hashlib
import sys
import zipfile
from natsort import natsorted, ns
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import paperstream.extract_framed_area as frame
import logging
from logging.config import fileConfig

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

DEBUG = False
fileConfig(resource_path("log_configuration.ini"))
LOGGER = logging.getLogger()

EXTRACTED_PAGES_DIR = resource_path("output/temporal/diary_pages/")
EXTRACTED_AREAS_DIR = resource_path("output/temporal/answers_areas/")
EXTRACTED_MARK_DIR = resource_path("output/temporal/mark_areas/")
ENCODED_DIARIES_DIR = resource_path("output/encoded_diaries/")


# Percentage of black pixels that must be different between two answer marks to consider it answered
MARK_BLACK_THRESHOLD = 1.3

#############################################################
#############################################################
#############################################################
#######################  Encode Diary ####################### 
#############################################################
#############################################################
#############################################################

def create_answer_space(x_coord, y_coord, radius, entry, variable, value, black_pixels):
    """Create an object representing an answer space"""
    anser_space = {}
    anser_space["x"] = x_coord
    anser_space["y"] = y_coord
    anser_space["radius"] = radius
    anser_space["entry"] = entry
    anser_space["variable"] = variable
    anser_space["value"] = value
    anser_space["black_pixels"] = black_pixels
    return anser_space


def load_answer_key_from_file(output_dir, rubric):
    """Load the answer key from a file """
    marks_storage = os.path.join(output_dir, "answer_key.json")
    if os.path.exists(marks_storage):
        with open(marks_storage, 'r') as file:
            answer_key = json.load(file)
            hash_object = hashlib.sha256(rubric.encode())
            key = hash_object.hexdigest()
            if key in answer_key:
                LOGGER.info("Answer key loaded from previous file " + marks_storage)
                return answer_key[key]
    return []

def save_answer_key_to_file(output_dir, rubric, answer_key):
    """Save the answer key to a file """
    marks_storage = os.path.join(output_dir, "answer_key.json")
    with open(marks_storage, 'w') as file:
        hash_object = hashlib.sha256(rubric.encode())
        key = hash_object.hexdigest()
        marks_per_rubric = {}
        marks_per_rubric[key] = answer_key
        file.write(json.dumps(marks_per_rubric))

def clean_image(img_path):
    """Clean a tif image using an adaptative threshold"""

    image = Image.open(img_path)
    cleaned_image = np.asarray(image)
    image.close()    
    
    r, g, b = cv2.split(cleaned_image)
    cleaned_image = cv2.merge([b, g, r])

    # Conver to a gray scale image
    imgray = cv2.cvtColor(cleaned_image, cv2.COLOR_BGR2GRAY)
    # Apply a blur filter
    cleaned_image = cv2.medianBlur(imgray, 5)
    # Apply the adaptative threshold gaussian correction
    cleaned_image = cv2.adaptiveThreshold(cleaned_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 51, 22)
    # Save the processed np array to an new file and load it again as an image
    clean_image_path = img_path.replace(".tif", "_a.tif")
    # clean_image_path = img_path
    cv2.imwrite(clean_image_path, cleaned_image)

    return clean_image_path

def create_answer_spaces_output_dir(answer_area_path):
    """Create and get the output folder for the answer spaces of the answer_area file"""

    # Each answer_area file is stored in a folder named after the Tif/png file from which it was
    # extracted. Get the name of that parent folder
    parent_dir_name = os.path.basename(os.path.dirname(answer_area_path))

    # This parent folder will be recreated under EXTRACTED_MARK_DIR
    parent_output_dir_path = os.path.join(EXTRACTED_MARK_DIR, parent_dir_name)
    if not os.path.exists(parent_output_dir_path):
        os.makedirs(parent_output_dir_path)

    # Since each answer_path can have multiple answer spaces we need a folder to store them.
    # We name this folder the same as the answer_area file
    page_output_dir = os.path.splitext(os.path.basename(answer_area_path))[0]

    # Therefore, the folder for each answer area answer space is stored in parent_output_dir_path
    page_output_path = os.path.join(parent_output_dir_path, page_output_dir)
    if not os.path.exists(page_output_path):
        os.makedirs(page_output_path)

    return page_output_path

def get_answer_headers(answer_key):
    headers = {}
    for answer in answer_key:
        headers[answer["variable"]] = True
    return sorted(list(headers.keys()))

def get_answer_key(answer_area_path, rubric):
    """Create the answer key to encode a diary based on a blank diary page and a rubirc

    Keyword arguments:
    answer_area_path -- the path to an image that contains the answers to be encoded
    rubric -- CSV with the encoding values of all answer spaces (entryID,variable,value,x,y,radius)
    """
    answer_spaces_output_path = create_answer_spaces_output_dir(answer_area_path)

    # If the answer_key already existis, use it
    answer_key = load_answer_key_from_file(answer_spaces_output_path, rubric)
    if answer_key != []:
        return answer_key

    answer_area = Image.open(clean_image(answer_area_path))

    # Calculate the factor scale, due the rubric being created at a resolution of 920x570
    base_height = 920
    base_width = 570
    height_scale = (float(answer_area.size[1])/base_height)
    width_scale = (float(answer_area.size[0])/base_width)

    for answer_space in rubric.split("\n"):
        # Parse the rubric
        answer_space = answer_space.split(",")
        radius = float(answer_space[5]) * height_scale
        x = (float(answer_space[3])) * width_scale
        y = (float(answer_space[4])) * height_scale
        answer_space_pixels = answer_area.crop((x - radius, y - radius, x + radius, y + radius))

        # Count the number of black pixels in the answer space
        black_pixels = 0
        for pixel in answer_space_pixels.getdata():
            if pixel == 0:
                black_pixels += 1

        # Save the answer_space image for debuggin purposes
        # answer_space_pixels.save(answer_spaces_output_path + \
        #                         "/img{0}-{1}-{2}.png".format(answer_space[0],
        #                                                      answer_space[1], answer_space[2]))

        # Save the created answer space to the answer key
        answer_key.append(create_answer_space(x, y, radius, answer_space[0], answer_space[1],
                                              answer_space[2], black_pixels))

    answer_area.close()
    # Save the answer key to a file to reuse it later
    save_answer_key_to_file(answer_spaces_output_path, rubric, answer_key)

    return answer_key

def mark_answer_area(answer_area_path, answer_key, date):
    """Encode an answer_area based on an answer_key"""

    encoded_answers = {}
    answer_area = Image.open(clean_image(answer_area_path))

    for answer in answer_key:
        answer_space = answer_area.crop((answer["x"] - answer["radius"],
                                         answer["y"] - answer["radius"],
                                         answer["x"] + answer["radius"],
                                         answer["y"] + answer["radius"]))

        # Count the number of pixels in the answer space
        black = 0
        for pixel in answer_space.getdata():
            if pixel == 0: #Pixel is either 0 or 255
                black += 1

        # If the number of black pixels is bigger than the template count times MARK_BLACK_THRESHOLD
        # count this answer as positive
        if black > (answer["black_pixels"] * MARK_BLACK_THRESHOLD):
            answer_key = "{}#{}".format(date.strftime("%Y-%m-%d"), answer["entry"])
            if answer_key not in encoded_answers:
                encoded_answers[answer_key] = {answer["variable"]: answer["value"]}
            else:
                if answer["variable"] not in encoded_answers[answer_key]:
                    encoded_answers[answer_key].update({answer["variable"]: answer["value"]})
                else:
                    encoded_answers[answer_key].update({answer["variable"]: "DUPLICATED"})

        # Save the answer_space image for debuggin purposes
        # answer_spaces_output_path = create_answer_spaces_output_dir(answer_area_path)
        # answer_space.save(answer_spaces_output_path + \
        #                "/img-{0}-{1}-{2}.png".format(answer["entry"],
        #                                              answer["variable"],
        #                                              answer["value"]))
    answer_area.close()
    return encoded_answers

def get_files_in_directory(directory_path, extension):
    """Get all files in a directory with extension"""
    files = [str(path) for path in Path(directory_path).glob("**/*{}".format(extension))]
    files = natsorted(files, alg=ns.PATH) 
    return files

def save_diary_answers(file_name, diary_answers, headers):
    """Saves diary_answers to a CSV file_name"""

    encoded_diary_path = ENCODED_DIARIES_DIR / Path(file_name + ".csv")
    with open(encoded_diary_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["date","entry"] + headers)
        for page_id, answers_entries in diary_answers.items():
            for date_entry, answers in answers_entries.items():
                row = date_entry.split("#") + [answers.get(variable, None) for variable in headers]

                # If there is a missing value, make it explicit
                row = ['MISSING' if value is None else value for value in row]
                writer.writerow(row)
    return encoded_diary_path

def encode_diary(diary_path, template_path,  rubric, starting_date):
    """Encodes a diary_path based on a rubric (from the web interface)

    Keyword arguments:
    diary_path -- the path to a multi-page tiff file (the scanned diary)
    rubric -- CSV with the encoding values of all answer spaces (entryID,variable,value,x,y,radius)
    starting_date -- each page of the encoded diary will be asigned a date starting from this value
    """
    # Get the first tif or png file in template_path (it should not have any pen marks)
    templates = get_files_in_directory(template_path, ".tif") + get_files_in_directory(template_path, ".png")
    encoding_template = templates[0]

    diary_path = Path(diary_path)
    LOGGER.info("Encoding {}".format(diary_path))
    

    # Get the answer area framed by the L-shaped markers of the encoding template
    answer_area_template = frame.extract_answer_area_from_page(encoding_template, EXTRACTED_PAGES_DIR, EXTRACTED_AREAS_DIR)[0]
    
    # Get the answer key to encode a diary (image coordinates with a black-pixels threshold)
    answer_key = get_answer_key(answer_area_template, rubric)
    file_headers = get_answer_headers(answer_key)
    
    # Get the answer areas from each page of the diary to encode
    answer_areas_all_pages = frame.extract_answer_area_from_page(diary_path, EXTRACTED_PAGES_DIR, EXTRACTED_AREAS_DIR)
    
    page_id = 1
    diary_answers = {}
    date = valid_date(starting_date)
    
    for answer_area in answer_areas_all_pages:
        diary_answers[str(page_id)] = mark_answer_area(answer_area, answer_key, date)
        page_id += 1
        date += datetime.timedelta(days=1)

    diary_answers_file = save_diary_answers(diary_path.stem, diary_answers, file_headers)
    return diary_answers_file

def valid_date(string_date):
    """Get a valid date from a string in format DD/MM/YYY"""
    try:
        return datetime.datetime.strptime(string_date, "%d/%m/%Y")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(string_date)