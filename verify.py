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
from check_missing import check_missing, check_no_raw

def verify(do_flush):
    """ Verify sanity of data. """

    # Check missing images since 1947 -- should be zero.
    arguments = {"min": 80, "max": 0, "chamber": "", "name": "",
                 "state": "", "sort": "congress", "type": "flat",
                 "year": False, "raw": False, "group": ""}
    number_missing_current = check_missing(arguments)

    # Check missing raw images
    number_missing_raw = len(check_no_raw(1))

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
        images = set([x[-3] for x in members])

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

    if number_missing_raw:
        print(("Soft warning: Missing %d raw images for "
               "represented final images." % number_missing_raw))

    if multiple_set:
        print(("Soft warning: Some images have multiple sources. "
               "Remove manual or wiki sources in favor of official sources."))
        print(multiple_set)

    if any([number_missing_current > 1,
            diff_set,
            photos_missing,
            len(unknown_provenance) > 4]):
        print("We have one or more data integrity issues.")

        if number_missing_current:
            print("Missing %d images for modern "
                  "members." % number_missing_current)
        if diff_set:
            print("Some images we possess are not represented in members file.")
            print(diff_set)
            if do_flush:
                for i in diff_set:
                    if i.rsplit("/", 1)[1] in multiple_set:
                        os.unlink(i)
                        i_out = (i.replace("images/", "images/raw/")
                                 .replace(".jpg", ".*"))
                        for file in glob.glob(i_out):
                            os.unlink(file)
                    else:
                        print(("%s not included in members file, but not a "
                               "duplicate either. Regenerate members file "
                               "with `config/dump_csv.py`?" % i))

                print("Flushed those files.")

        if photos_missing:
            print("Some images in the members file are not in our possession.")
            print(list(photos_missing)[0:10])
        if len(unknown_provenance) > 4:
            print("Some members have no provenance statement for their image.")
            print(unknown_provenance)

        sys.exit(1)

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
