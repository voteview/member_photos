""" Tests integrity of output. """

from __future__ import print_function
from collections import Counter
import csv
import glob
import json
import os
import sys
import traceback
import argparse
import six
import prettytable
from wand.image import Image
from check_missing import check_missing, check_no_raw

def verify(do_flush):
    """ Verify sanity of data. """

    # Check missing images since 1947 -- should be zero.
    arguments = {"min": 80, "max": 0, "chamber": "", "name": "",
                 "state": "", "sort": "congress", "type": "flat",
                 "year": False, "raw": False, "group": ""}
    number_missing_current = check_missing(arguments)

    # Check missing raw images
    missing_raw = check_no_raw(1)

    # Check that everyone in the members file has a photo and every
    # photo has an entry in the members file.
    all_exposed_photos = (set(glob.glob("images/bio_guide/*")) |
                          set(glob.glob("images/wiki/*")) |
                          set(glob.glob("images/manual/*")))

    # Check integrity of provenance file.
    try:
        json.load(open("config/provenance.json", "r"))
    except json.JSONDecodeError:
        print("Data integrity error: Invalid provenance file")
        print(traceback.format_exc())
        sys.exit(1)

    # Try to load member csv
    error = 0
    try:
        # Read the member CSV and get members -- also checks CSV integrity
        with open("members.csv", "r") as member_csv:
            member_reader = csv.reader(member_csv,
                                       delimiter=",",
                                       quotechar='"')
            members = [x for x in member_reader][1:]

        # Isolate images claimed
        images = {x[-3] for x in members}

        # How many unknown provenance
        unknown_provenance = [x for x in members
                              if x[-1] == "Unknown Provenance [!]"]

        # How many do we have files but not entries for?
        diff_set = all_exposed_photos - images

        # How many do we have entries but not files for?
        photos_missing = images - all_exposed_photos
    except Exception:
        print(traceback.format_exc())
        error = 1

    # Do we have anyone in multiple sets of data?
    type_count = Counter([x.rsplit("/", 1)[1]
                          for x in (glob.glob("images/bio_guide/*") +
                                    glob.glob("images/wiki/*") +
                                    glob.glob("images/manual/*"))])
    multiple_set = [k for k, v in six.iteritems(type_count) if v > 1]

    if error:
        print("Error reading CSV file.")
        sys.exit(1)

    if not os.path.isfile("config/facial_recognition.json"):
        print("Soft warning: No facial recognition API keys found.")

    if missing_raw:
        print(("Soft warning: Missing %d raw images for "
               "represented final images." % len(missing_raw)))
        if len(missing_raw) < 4:
            print(missing_raw)

    if multiple_set:
        print(("Soft warning: Some images have multiple sources. "
               "Remove manual or wiki sources in favor of official sources."))
        print(multiple_set)

    awkward_images = check_aspect_ratio()
    if awkward_images:
        print(("Some images with awkward aspect ratios. "
               "Worst examples: "))
        print(awkward_images.get_string(sortby="delta", reversesort=True, end=20))

    if not any([number_missing_current > 1, diff_set, photos_missing,
                unknown_provenance]):
        return

    print("We have one or more data integrity issues.")

    if number_missing_current:
        print("Missing %d images for modern "
              "members." % number_missing_current)

    if diff_set:
        print("Some images we possess are not represented in members file.")
        print(diff_set)
        if do_flush:
            flush_files(diff_set, multiple_set)

    if photos_missing:
        print("Some images in the members file are not in our possession.")
        print(list(photos_missing)[0:10])

    if unknown_provenance:
        print("Some members have no provenance statement for their image.")
        print(unknown_provenance)

    sys.exit(1)

def check_aspect_ratio():
    """ Check images with bad aspect ratios. """
    bioguide_images = glob.glob("images/bio_guide/*.*")
    results = []

    for image in bioguide_images:
        if image.rsplit("/", 1)[1][0:2] not in ["02", "03", "04", "09"]:
            continue
        with Image(filename=image) as img_in:
            aspect_ratio = round(float(img_in.size[0]) / float(img_in.size[1]), 2)
            if 0.7 <= aspect_ratio <= 0.9:
                continue
            results.append([image.rsplit("/", 1)[1].split(".", 1)[0],
                            aspect_ratio,
                            abs(aspect_ratio - 0.8),
                            "%sx%s" % (img_in.size[0], img_in.size[1])])

    if not results:
        return []

    results.sort(key=lambda x: -x[2])

    table_out = prettytable.PrettyTable(
        ["ICPSR", "Aspect Ratio", "delta", "Resolution"]
    )
    for row in results:
        table_out.add_row(row)

    return table_out

def flush_files(diff_set, multiple_set):
    """ Performs flushing of extra or duplicate files. """
    for i in diff_set:
        if i.rsplit("/", 1)[1] in multiple_set:
            os.unlink(i)
            i_out = i.replace("images/", "images/raw/").replace(".jpg", ".*")
            for file in glob.glob(i_out):
                os.unlink(file)
        else:
            print(("%s not included in members file, but not a "
                   "duplicate either. Regenerate members file "
                   "with `config/dump_csv.py`?" % i))

    print("Flushed those files.")


def parse_arguments():
    """ Parse command line arguments and launch the process. """
    parser = argparse.ArgumentParser(
        description="Verify integrity of database."
    )
    parser.add_argument("--flush", action="store_true")
    arguments = parser.parse_args()

    verify(arguments.flush)

if __name__ == "__main__":
    parse_arguments()
