""" Scrapes Congressional Bio Guide and saves images. """

from __future__ import print_function
import argparse
import json
import glob
import os
import shutil
from pymongo import MongoClient
import bs4
import requests

def get_blacklist():
    """ Reads blacklist and returns it. """
    return json.load(open("config/bio_guide_results.json", "r"))

def get_config():
    """ Reads config file and returns it. """
    config = json.load(open("config/config.json", "r"))
    return config

def list_images():
    """ Checks images subdirectory for all ICPSRs. """
    processed = set([x.rsplit("/", 1)[1].split(".")[0]
                     for x in glob.glob("images/bio_guide/*.*")])
    raw = set([x.rsplit("/", 1)[1].split(".")[0]
               for x in glob.glob("images/raw/bio_guide/*.*")])
    return processed | raw

def get_missing_mongo(min_congress):
    """ Check which ICPSRs in our query are actually missing from Mongo DB. """

    # Connect
    config = get_config()
    connection = MongoClient(config["db_host"], config["db_port"])
    cursor = connection["voteview"]

    query = {"bioguide_id": {"$exists": True},
             "congress": {"$gte": min_congress}}

    present_set = list_images()
    blacklist = get_blacklist()
    person_set = []
    icpsr_set = []
    filter_return = {"bioguide_id": 1, "bioname": 1, "congress": 1, "icpsr": 1}
    for row in cursor.voteview_members.find(query, filter_return,
                                            no_cursor_timeout=True):
        # Because same ICPSR can be recycled, keep a running list of
        # viewed ICPSRs
        if row.get("icpsr", 0) not in icpsr_set:
            new_entry = [str(row["icpsr"]).zfill(6), row["bioguide_id"]]
            person_set.append(new_entry)
            icpsr_set.append(row["icpsr"])

    icpsr_zfill = set([x[0] for x in person_set])
    missing = icpsr_zfill - present_set - set(blacklist["blacklist"])

    return [x for x in person_set if x[0] in missing]

def get_missing_flat(min_congress):
    """ Check which ICPSRs in our query are actually missing from flat file. """

    # All people
    people = json.load(open("config/database-raw.json", "r"))

    # Min match
    people = [[x["icpsr"], x["bioguide_id"]]
              for x in people
              if x["congress"] >= min_congress and "bioguide_id" in x]

    # Now exclude found results
    present_set = set(list_images()) | set(get_blacklist()["blacklist"])

    return [x for x in people if str(x[0]).zfill(6) not in present_set]

def save_image(icpsr, extension, data):
    """ Simple helper to do a binary file write. """

    # Make directory if necessary
    full_dir = os.path.dirname("images/raw/bio_guide/")
    if not os.path.exists(full_dir):
        os.makedirs(full_dir)

    # Write the binary data.
    with open("images/raw/bio_guide/%s.%s" %
              (icpsr, extension), "wb") as out_file:
        shutil.copyfileobj(data, out_file)

def individual_lookup(icpsr, bioguide_id):
    """ Takes bioguide_id and icpsr and gets image. """

    config = get_config()
    lookup_url = config["bio_guide_url"]

    # Load congress bio page
    page_request = requests.get(lookup_url + bioguide_id).text
    parser = bs4.BeautifulSoup(page_request, "html.parser")

    # List images on page and extract
    images = parser.find_all("img")[1:]
    if images:
        print("\t Found image, checking to see if placeholder!")
        extension = images[0]["src"].split(".")[-1]
        url = config["bio_guide_base"] + images[0]["src"]
        if "nophoto.jpg" not in images[0]["src"]:
            binary_download = requests.get(url, stream=True)
            save_image(icpsr, extension, binary_download.raw)
            print("\t OK, downloaded!")
        else:
            print("\t Placeholder only, skipping")
    else:
        print("\t No image")

def main_loop(db_type, min_congress):
    """
    Get missing members and scrape a photo for each of them from the
    bio guide.
    """

    if db_type == "flat":
        missing_icpsrs = get_missing_flat(min_congress)
    else:
        missing_icpsrs = get_missing_mongo(min_congress)

    # Iterate through the set.
    i = 1
    for person in missing_icpsrs:
        # Expand, print
        icpsr, bioguide_id = person
        print("Lookup for icpsr %s (bio guide ID %s)... %d/%d" %
              (icpsr, bioguide_id, i, len(missing_icpsrs)))
        individual_lookup(icpsr, bioguide_id)
        i = i + 1

def single_download(db_type, icpsr):
    """ Download a single ICPSR. """

    if db_type == "flat":
        people = json.load(open("config/database-raw.json", "r"))
        bioguide_id = next(x["bioguide_id"]
                           for x in people
                           if x["icpsr"] == icpsr and "bioguide_id" in x)
        if bioguide_id:
            individual_lookup(str(icpsr).zfill(6), bioguide_id)
        else:
            print("No bioguide information for ICPSR %s" % icpsr)

        return

    # Connect
    config = get_config()
    connection = MongoClient(config["db_host"], config["db_port"])
    cursor = connection["voteview"]

    query = {"bioguide_id": {"$exists": True}, "icpsr": icpsr}
    result = cursor.voteview_members.find_one(query,
                                              {"bioguide_id": 1, "_id": 0})
    if result:
        individual_lookup(str(icpsr).zfill(6), result["bioguide_id"])
    else:
        print("No bioguide information for ICPSR %s" % icpsr)

    return

def process_arguments():
    """ Handles getting the arguments from command line. """
    parser = argparse.ArgumentParser(description="Scrapes Congressional Bioguide for Bio Images")
    parser.add_argument("--min", type=int, nargs="?", default=105)
    parser.add_argument("--type", type=str, default="mongo", nargs="?")
    parser.add_argument("--icpsr", type=int, nargs="?")
    arguments = parser.parse_args()

    if arguments.icpsr:
        single_download(arguments.type, arguments.icpsr)
    else:
        main_loop(arguments.type, arguments.min)


if __name__ == "__main__":
    process_arguments()
