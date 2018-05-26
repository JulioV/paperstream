"""
Encode a diary. The diary must be scanned into a tiff/png file. The rubric to encode it must be
created through the web interface.

Julio Vega
"""
import math
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

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

EXTRACTED_PAGES_DIR = resource_path("output/temporal/diary_pages/")
EXTRACTED_AREAS_DIR = resource_path("output/temporal/answers_areas/")
EXTRACTED_MARK_DIR = resource_path("output/temporal/mark_areas/")
ENCODED_DIARIES_DIR = resource_path("output/encoded_diaries/")
DIARIES_TO_CREATE_DIR = resource_path("input/1_diaries_to_create/")
TEMPLATE_DIR = resource_path("input/2_template_to_encode/")
DIARIES_TO_ENCODE_DIR = resource_path("input/3_diaries_to_encode/")

#############################################################
#############################################################
#############################################################
# Extract a section of an image framed by 4 L-shaped markers
#############################################################
#############################################################
#############################################################
# This script was adapted from the work done by Raphael Baron https://github.com/rbaron/omr

# Threasholds to identify the corner markers (hull area, hull perimeter, bounding box area)
MARKERS_THRESHOLDS = (12500, 850, 45000)

# Width of the extracted area image in pixels
AREA_IMAGE_WIDTH = 2048

# Separation between horizontal L-shaped corner marks is 340, between vertical ones is 548
AREA_IMAGE_HEIGHT = math.ceil(AREA_IMAGE_WIDTH * (548/340.0))

# Percentage of black pixels that must be different between two answer marks to consider it answered
MARK_BLACK_THRESHOLD = 1.3

def normalize(im):
    return cv2.normalize(im, np.zeros(im.shape), 0, 255, norm_type=cv2.NORM_MINMAX)

def get_approx_contour(contour, tol=.01):
    """Get rid of 'useless' points in the contour"""
    epsilon = tol * cv2.arcLength(contour, True)
    return cv2.approxPolyDP(contour, epsilon, True)

def features_distance(features_contour, features_reference):
    """Get the norm between the features of each contour and the reference features"""
    return np.linalg.norm(np.array(features_contour) - np.array(features_reference))

def get_contours(image_gray):
    """Get contours in image"""
    # Image_gray can be a good candidate to "binarise" the scanned image for better recognition
    im2, contours, hierarchy = cv2.findContours(
        image_gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    return list(map(get_approx_contour, contours))

def get_features(contour):
    """Get the three features that identify a corner marker"""
    try:
        return (cv2.contourArea(contour),
                cv2.arcLength(contour, True),
                cv2.contourArea(get_bounding_rect(contour)))
    except ZeroDivisionError:
        #return 4*[np.inf]
        return 4*[0]

def get_corners(contours):
    """Get the four corner markers filtering them by their feature thresholds"""
    return sorted(
        contours,
        key=lambda c: features_distance(MARKERS_THRESHOLDS, get_features(c)))[:4]

def order_points(points):
    """Order points counter-clockwise-ly."""
    origin = np.mean(points, axis=0)

    def positive_angle(angle_p):
        x, y = angle_p - origin
        ang = np.arctan2(y, x)
        return 2 * np.pi + ang if ang < 0 else ang

    return sorted(points, key=positive_angle)

def get_bounding_rect(contour):
    """Get the bounding rectangle"""
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    return np.int0(box)

def get_outmost_points(contours):
    """Get the bounding rectangle of all the contours"""
    all_points = np.concatenate(contours)
    return get_bounding_rect(all_points)

def perspective_transform(img, points):
    """Transform img so that points are the new corners"""
    source = np.array(
        points,
        dtype="float32")

    dest = np.array([
        [AREA_IMAGE_WIDTH, AREA_IMAGE_HEIGHT],
        [0, AREA_IMAGE_HEIGHT],
        [0, 0],
        [AREA_IMAGE_WIDTH, 0]],
                    dtype="float32")

    img_dest = img.copy()
    transf = cv2.getPerspectiveTransform(source, dest)
    warped = cv2.warpPerspective(img, transf, (AREA_IMAGE_WIDTH, AREA_IMAGE_HEIGHT))
    return warped

def get_first_page_answer_area(source_file):
    """Get the answer area of the first page of source_file as an image"""
    areas_path = extract_answer_areas_from_image(source_file, page_limit=1)
    return cv2.imread(areas_path[0])

def save_individual_pages_to_disk(diary):
    file_name, extension = os.path.splitext(os.path.basename(diary))
    save_dir = os.path.join(EXTRACTED_PAGES_DIR, file_name)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    images_paths = []

    if extension == ".png":
        images_paths.append(diary)
    elif extension == ".zip":
        zip_ref = zipfile.ZipFile(diary, 'r')
        zip_ref.extractall(save_dir)
        zip_ref.close()
        unzipped_pages = get_files_in_directory(save_dir, ".png")
        images_paths += unzipped_pages
    elif extension == ".tif":
        img = Image.open(diary)
        pages = img.n_frames
        for i in range(0, pages):
            img.seek(i)
            page_path = os.path.join(save_dir, "page_{}.tif".format(i))
            # Save individual pages as images
            img.save(page_path)
            images_paths.append(page_path)

    return images_paths

def extract_answer_areas_from_image(source_file, print_corner_markers=False, page_limit=0):
    """Extracts as single images the answer areas of each page of source_fle (a tiff file)
    Returns a list with the path to each area file.abs

    Run the full pipeline:

        - Load image
        - Convert to grayscale
        - Filter out high frequencies with a Gaussian kernel
        - Apply threshold
        - Find contours
        - Find corners among all contours
        - Find 'outmost' points of all corners
        - Apply perpsective transform to get a bird's eye view
        - Save each area to a file
    """
    extracted_answer_area_paths = []
    individual_pages_paths = (save_individual_pages_to_disk(source_file))

    page_number = 0
    for page_path in individual_pages_paths:
        if page_limit == 0 or (page_limit > 0 and page_number < page_limit):
            try:
                # Load page as an Open CV image
                original_image = cv2.imread(page_path)

                # Transform the image
                blurred_image = cv2.GaussianBlur(original_image, (11, 11), 10)
                normalised_image = normalize(cv2.cvtColor(blurred_image, cv2.COLOR_BGR2GRAY))
                ret, binary_image = cv2.threshold(normalised_image, 127, 255, cv2.THRESH_BINARY)

                # Get the image black contours
                contours = get_contours(binary_image)

                # Identify the corners from the contours
                corners = get_corners(contours)

                # Save the image with contours for debuggin purposes
                cv2.drawContours(original_image, corners, -1, (0, 255, 0), 3)
                if print_corner_markers:
                    cv2.imwrite(EXTRACTED_PAGES_DIR + "page_contours{}.tif".format(page_number), original_image)

                # Get the area_markers that frame the answer area of a page
                area_markers = order_points(get_outmost_points(corners))

                # Get the answer area of a pge
                extracted_area = perspective_transform(original_image, area_markers)

                # Get the path to save the answer area
                diary_file_name = os.path.splitext(os.path.basename(source_file))[0]

                # Create folder to save the individual answer areas
                extracted_pages_folder = os.path.join(EXTRACTED_AREAS_DIR, diary_file_name)
                if not os.path.exists(extracted_pages_folder):
                    os.makedirs(extracted_pages_folder)

                # Save the current answer_area to a file
                extracted_answer_area_path = os.path.join(extracted_pages_folder, "answer_area_page_{}.tif".format(page_number))
                cv2.imwrite(extracted_answer_area_path, extracted_area)

                # Save the path of the extracted answer area
                extracted_answer_area_paths.append(extracted_answer_area_path)

            except EOFError as error:
                print(error)
        page_number += 1
    return extracted_answer_area_paths

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
                print("Marks loaded from file: " + marks_storage)
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

    answer_area_path = img_path
    answer_area = Image.open(answer_area_path)
    answer_area = np.asarray(answer_area)
    r, g, b = cv2.split(answer_area)
    answer_area = cv2.merge([b, g, r])

    # Conver to a gray scale image
    imgray = cv2.cvtColor(answer_area, cv2.COLOR_BGR2GRAY)
    # Apply a blur filter
    answer_area = cv2.medianBlur(imgray, 5)
    # Apply the adaptative threshold gaussian correction
    answer_area = cv2.adaptiveThreshold(answer_area, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 51, 22)
    # Save the processed np array to an new file and load it again as an image
    cv2.imwrite(answer_area_path.replace(".tif", "_a.tif"), answer_area)
    answer_area = Image.open(answer_area_path.replace(".tif", "_a.tif"))

    return answer_area

def create_answer_spaces_output_dir(answer_area_path):
    """Create and get the output folder for the answer spaces of the answer_area file"""

    # Each answer_area file is stored in a folder named after the Tif file from which it was
    # extracted. Get the name of that parent folder
    parent_dir_name = os.path.dirname(answer_area_path)
    parent_dir_name = os.path.basename(parent_dir_name)

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

    answer_area = clean_image(answer_area_path)

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
        answer_space_pixels.save(answer_spaces_output_path + \
                                "/img{0}-{1}-{2}.png".format(answer_space[0],
                                                             answer_space[1], answer_space[2]))

        # Save the created answer space to the answer key
        answer_key.append(create_answer_space(x, y, radius, answer_space[0], answer_space[1],
                                              answer_space[2], black_pixels))

    # Save the answer key to a file to reuse it later
    save_answer_key_to_file(answer_spaces_output_path, rubric, answer_key)

    return answer_key

def encode_page(answer_area_path, answer_key, date):
    """Encode an answer_area based on an answer_key"""

    encoded_answers = []
    encoded_answers2 = {}
    answer_area = clean_image(answer_area_path)

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
            #diff = black / answer["black_pixels"]
            answer_key = "{}#{}".format(date.strftime("%Y-%m-%d"), answer["entry"])
            if answer_key not in encoded_answers2:
                encoded_answers2[answer_key] = {answer["variable"]: answer["value"]}
            else:
                if answer["variable"] not in encoded_answers2[answer_key]:
                    encoded_answers2[answer_key].update({answer["variable"]: answer["value"]})
                else:
                    encoded_answers2[answer_key].update({answer["variable"]: "DUPLICATED"})
            encoded_answers.append([date.strftime("%Y-%m-%d"),
                                    answer["entry"],
                                    answer["variable"],
                                    answer["value"]])

        # Save the answer_space image for debuggin purposes
        answer_spaces_output_path = create_answer_spaces_output_dir(answer_area_path)
        answer_space.save(answer_spaces_output_path + \
                       "/img-{0}-{1}-{2}.png".format(answer["entry"],
                                                     answer["variable"],
                                                     answer["value"]))

    return encoded_answers2

def get_files_in_directory(directory_path, extension):
    """Get all files in a directory with extension"""

    files = [str(path) for path in Path(directory_path).glob("**/*{}".format(extension))]
    files = natsorted(files, alg=ns.PATH) 

    return files

def save_encoded_answers(file_name, diary_answers):
    """Saves diary_answers to a CSV file_name"""

    encoded_diary_path = os.path.join(ENCODED_DIARIES_DIR, file_name + ".csv")
    with open(encoded_diary_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["date","entry","hour","ampm","minute","symptomA","symptomB","symptomC"])
        for page, answers in diary_answers.items():
            for key, values in answers.items():
                row = key.split("#") + [values.get("hh"), values.get("day"), values.get("mm"), 
                                 values.get("s1"), values.get("s2"), values.get("s3")]
                
                # If there is a missing value, make it explicit
                row = ['MISSING' if v is None else v for v in row]
                writer.writerow(row)
    return encoded_diary_path

def encode_diary(diary_path, rubric, starting_date):
    """Encodes a diary_path based on a rubric (from the web interface) and encoding_template.

    Keyword arguments:
    diary_path -- the path to a multi-page tiff file (the scanned diary)
    rubric -- CSV with the encoding values of all answer spaces (entryID,variable,value,x,y,radius)
    encoding_template -- the path to a one page tiff file (the scanned diary without pen marks)
    starting_date -- each page of the encoded diary will be asigned a date starting from this.
    """
    # Get the first tif file in TEMPLATE_DIR (it should not have any pen marks)
    tif_files = get_files_in_directory(TEMPLATE_DIR, ".tif")
    if tif_files:
        encoding_template = tif_files[0]
    else:
        encoding_template = get_files_in_directory(TEMPLATE_DIR, ".png")[0]

    
    # Get the answer area framed by the L-shaped corners of the first page of the encoding template
    answer_area_path = extract_answer_areas_from_image(encoding_template)[0]
    
    # Get the answer key based on a template and the rubric (answer spaces and their values)
    answer_key = get_answer_key(answer_area_path, rubric)

    # Get the answer areas from each page of the diary to encode
    answer_areas_all_pages = extract_answer_areas_from_image(diary_path)
    
    page_id = 1
    diary_encoded_answers = {}
    date = starting_date
    for page_answer_area in answer_areas_all_pages:
        print("Encoding page: " +  page_answer_area)
        page_encoded_answers = encode_page(page_answer_area, answer_key, date)
        diary_encoded_answers["{}".format(page_id)] = page_encoded_answers
        page_id += 1
        date += datetime.timedelta(days=1)

    # Save the coded answers to a file
    file_name = os.path.basename(os.path.splitext(diary_path)[0])
    encoded_diary = save_encoded_answers(file_name, diary_encoded_answers)

    return encoded_diary



def encode_diaries(rubric, starting_date):
    """Encode all the tiff files (diaries) in .input/diaries_to_encode """
    encoding_template = get_files_in_directory(TEMPLATE_DIR, ".tif")[0]

    diaries_encoded_answers = {}
    for diary_path in get_files_in_directory(DIARIES_TO_ENCODE_DIR, ".tif"):
        filename = os.path.basename(diary_path)
        diary_answers = encode_diary(diary_path, rubric, starting_date)
        diaries_encoded_answers[filename] = diary_answers
    return diaries_encoded_answers

def valid_date(string_date):
    """Get a valid date from a string in format DD/MM/YYY"""
    try:
        return datetime.datetime.strptime(string_date, "%d/%m/%Y")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(string_date)

def main():
    """Main method. Everything on this module is self-suficient except for the rubric
    A rubric can be built using the web interface. See static/index.html"""

    # Example of encoding and a rubirc (you usually generate it on the web interface). ONLY FOR TESTING
    # rubric = "0,hh,12,78.99300699,176.9956522,12\n0,hh,1,111.98601399,183.9956522,12\n0,hh,2,132,208.0065217,12\n0,hh,3,141.9895105,235.9978261,12\n0,hh,4,132.986014,268.9956522,12\n0,hh,5,112.9895105,291.0065217,12\n0,hh,6,79.99300699,299.9978261,12\n0,hh,7,47.98951049,290,12\n0,hh,8,27.98251748,268.9586957,12\n0,hh,9,19.982517483,237.9913043,12\n0,hh,10,27.9965035,207.9891304,12\n0,hh,11,46.98951049,184.9695652,12\n0,day,am,79.99300699,218.9913043,12\n0,day,pm,78.98951049,257.9913043,12\n0,mm,0,179.9895105,176.9934783,12\n0,mm,15,180.993007,217.9956522,12\n0,mm,30,179.993007,258.9956522,12\n0,mm,45,180.9895105,300.9956522,12\n0,s1,0,369.993007,163.9956522,12\n0,s1,1,408.9895105,163.9956522,12\n0,s1,2,446.9895105,163.9934783,12\n0,s1,3,485.993007,164.9978261,12\n0,s2,3,486.9895105,225.9978261,12\n0,s2,2,447.9895105,224.9978261,12\n0,s2,1,407.9895105,224.9978261,12\n0,s2,0,369.993007,224.9978261,12\n0,s3,0,370.9895105,287.9978261,12\n0,s3,1,408.993007,287.9956522,12\n0,s3,2,446.993007,288.9934783,12\n0,s3,3,486.9895105,288.9956522,12\n1,hh,12,79.98951049,465.5652174,12\n1,hh,1,112.9825175,472.5652174,12\n1,hh,2,132.99650350000002,496.576087,12\n1,hh,3,142.986014,524.5673913,12\n1,hh,4,133.9825175,557.5652174,12\n1,hh,5,113.986014,579.576087,12\n1,hh,6,80.98951049,588.5673913,12\n1,hh,7,48.98601399,578.5695652,12\n1,hh,8,28.97902098,557.5282609,12\n1,hh,9,20.979020978999998,526.5608696,12\n1,hh,10,28.99300699,496.5586957,12\n1,hh,11,47.98601399,473.5391304,12\n1,day,am,80.98951049,507.5608696,12\n1,day,pm,79.98601399,546.5608696,12\n1,mm,0,180.986014,465.5630435,12\n1,mm,15,181.9895105,506.5652174,12\n1,mm,30,180.9895105,547.5652174,12\n1,mm,45,181.986014,589.5652174,12\n1,s1,0,370.9895105,452.5652174,12\n1,s1,1,409.986014,452.5652174,12\n1,s1,2,447.986014,452.5630435,12\n1,s1,3,486.9895105,453.5673913,12\n1,s2,3,487.986014,514.5673913,12\n1,s2,2,448.986014,513.5673913,12\n1,s2,1,408.986014,513.5673913,12\n1,s2,0,370.9895105,513.5673913,12\n1,s3,0,371.986014,576.5673913,12\n1,s3,1,409.9895105,576.5652174,12\n1,s3,2,447.9895105,577.5630435,12\n1,s3,3,487.986014,577.5652174,12\n2,hh,12,79.98951049,689.0782609,12\n2,hh,1,112.9825175,696.0782609,12\n2,hh,2,132.99650350000002,720.0891304,12\n2,hh,3,142.986014,748.0804348,12\n2,hh,4,133.9825175,781.0782609,12\n2,hh,5,113.986014,803.0891304,12\n2,hh,6,80.98951049,812.0804348,12\n2,hh,7,48.98601399,802.0826087,12\n2,hh,8,28.97902098,781.0413043,12\n2,hh,9,20.979020978999998,750.073913,12\n2,hh,10,28.99300699,720.0717391,12\n2,hh,11,47.98601399,697.0521739,12\n2,day,am,80.98951049,731.073913,12\n2,day,pm,79.98601399,770.073913,12\n2,mm,0,180.986014,689.076087,12\n2,mm,15,181.9895105,730.0782609,12\n2,mm,30,180.9895105,771.0782609,12\n2,mm,45,181.986014,813.0782609,12\n2,s1,0,370.9895105,676.0782609,12\n2,s1,1,409.986014,676.0782609,12\n2,s1,2,447.986014,676.076087,12\n2,s1,3,486.9895105,677.0804348,12\n2,s2,3,487.986014,738.0804348,12\n2,s2,2,448.986014,737.0804348,12\n2,s2,1,408.986014,737.0804348,12\n2,s2,0,370.9895105,737.0804348,12\n2,s3,0,371.986014,800.0804348,12\n2,s3,1,409.9895105,800.0782609,12\n2,s3,2,447.9895105,801.076087,12\n2,s3,3,487.986014,801.0782609,12"
    # diaries_encoded_answers = encode_diary(r"C:\Users\julio\Documents\phd\skip\src\diary\paperstream\paperstream\input\3_diaries_to_encode\P05.zip", rubric, valid_date("01/10/2017"))
    # print(diaries_encoded_answers)
    print(get_files_in_directory(r'C:\Users\julio\Documents\phd\skip\src\diary\paperstream\paperstream\output\temporal\diary_pages\P01\P01', '.png'))
if __name__ == '__main__':
    main()
