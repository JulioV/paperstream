import math
import cv2
import numpy as np
import os
import zipfile
from pathlib import Path
from natsort import natsorted, ns
from PIL import Image, ImageOps, ImageDraw
import logging
from logging.config import fileConfig

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

def get_first_page_answer_area(source_file, EXTRACTED_PAGES_DIR, EXTRACTED_AREAS_DIR):
    """Get the answer area of the first page of source_file as an image"""
    areas_path = extract_answer_area_from_page(source_file, EXTRACTED_PAGES_DIR, EXTRACTED_AREAS_DIR, page_limit=1)
    return cv2.imread(areas_path[0])

def get_files_in_directory(directory_path, extension):
    """Get all files in a directory with extension"""
    files = [str(path) for path in Path(directory_path).glob("**/*{}".format(extension))]
    files = natsorted(files, alg=ns.PATH) 
    return files


def save_individual_pages_to_disk(diary, EXTRACTED_PAGES_DIR):
    file_name, extension = os.path.splitext(os.path.basename(diary))
    save_dir = os.path.join(EXTRACTED_PAGES_DIR, file_name)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    images_paths = []
    if extension == ".png":
        images_paths.append(diary)
    elif extension == ".zip":
        with  zipfile.ZipFile(str(diary), 'r') as zip_ref:
            zip_ref.extractall(save_dir)
        unzipped_pages = get_files_in_directory(save_dir, ".png")
        images_paths += unzipped_pages
    elif extension == ".tif":
        with Image.open(diary) as tif_img:
            pages = tif_img.n_frames
            for i in range(0, pages):
                tif_img.seek(i)
                page_path = os.path.join(save_dir, "page_{}.tif".format(i))
                # Save individual pages as images
                tif_img.save(page_path)
                images_paths.append(page_path)
    return images_paths

def extract_answer_area_from_page(source_file, EXTRACTED_PAGES_DIR, EXTRACTED_AREAS_DIR, print_corner_markers=False, page_limit=0):
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
    individual_pages_paths = save_individual_pages_to_disk(source_file, EXTRACTED_PAGES_DIR)
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
                fileConfig("log_configuration.ini")
                LOGGER = logging.getLogger()
                LOGGER.error("Error extracting answer areas" , exc_info=True)
        page_number += 1
    return extracted_answer_area_paths