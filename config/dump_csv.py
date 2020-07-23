""" Dump database (or flat file) to `members.csv`. """

from __future__ import print_function
import argparse
import csv
import glob
import json
from pymongo import MongoClient

CONFIG = {}

def get_provenance(padded_icpsr):
    """ Gets a provenance quote from the JSON. """
    global CONFIG
    if not CONFIG or "provenance" not in CONFIG:
        CONFIG["provenance"] = json.load(open("provenance.json", "r"))

    for key, value in CONFIG["provenance"].iteritems():
        if padded_icpsr in value:
            return key

    return "Unknown Provenance [!]"

def party_name(party_code):
    """ Converts party code to a party name. """
    global CONFIG
    if not CONFIG or "party_data" not in CONFIG:
        CONFIG["party_data"] = json.load(open("parties.json", "r"))

    results = next((x for x in CONFIG["party_data"]
                    if x["party_code"] == party_code), None)
    return "Error" if results is None else results["full_name"]

def state_name(state_abbrev):
    """ Converts state abbreviation to a full name. """
    global CONFIG
    if not CONFIG or "state_data" not in CONFIG:
        CONFIG["state_data"] = json.load(open("states.json", "r"))

    results = next((x for x in CONFIG["state_data"]
                    if x["state_abbrev"].lower() == state_abbrev.lower()), None)
    return "Error" if results is None else results["name"]

def image_cache():
    """ Generates an image cache. """
    local_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
                        for x in glob.glob("../images/*/*.*")])
    return local_images

def do_dump_flat():
    """ Identifies those in the flatfile database that we have images for. """

    images = image_cache()
    people = json.load(open("database-raw.json", "r"))
    return [x for x in people if str(x["icpsr"]).zfill(6) in images]

def get_config():
    """ Reads config file and returns it. """
    config = json.load(open("config/config.json", "r"))
    return config

def do_dump_mongo():
    """ Identifies those in the mongo database that we have images for. """

    config = get_config()
    connection = MongoClient(config["db_host"], config["db_port"])
    cursor = connection["voteview"]

    fields_keep = {x: 1 for x in
                   ["icpsr", "bioname", "congress", "chamber",
                    "state_abbrev", "party_code", "born", "died"]}
    fields_keep["_id"] = 0

    images = image_cache()
    seen_icpsr = []
    results = []
    for result in (cursor.voteview_members.find({}, fields_keep)
                   .sort([("congress", -1)])):
        if result["icpsr"] in seen_icpsr:
            continue
        if str(result["icpsr"]).zfill(6) not in images:
            continue
        seen_icpsr.append(result["icpsr"])
        results.append(result)

    return results

def do_dump(db_type):
    """ Dump the data into a CSV along with image information. """
    images = image_cache()

    print("Getting database information.")
    if db_type == "flat":
        people = do_dump_flat()
    else:
        people = do_dump_mongo()
    print("Matching representatives to images.")

    csv_rows = []
    bio_images = [x.rsplit("/", 1)[1].rsplit(".", 1)[0]
                  for x in glob.glob("../images/bio_guide/*.jpg")]
    wiki_images = [x.rsplit("/", 1)[1].rsplit(".", 1)[0]
                   for x in glob.glob("../images/wiki/*.jpg")]
    # manual_images = [x.rsplit("/", 1)[1].rsplit(".", 1)[0]
    #                 for x in glob.glob("../images/manual/*.jpg")]

    for person in people:
        padded_icpsr = str(person["icpsr"]).zfill(6)
        if padded_icpsr not in images:
            continue

        # Which of the primary sources did this use?
        if padded_icpsr in bio_images:
            source = "bio_guide"
        elif padded_icpsr in wiki_images:
            source = "wiki"
        else:
            source = "manual"

        provenance = "" if source != "manual" else get_provenance(padded_icpsr)
        image = "images/%s/%s.jpg" % (source, padded_icpsr)

        out_data = {
            "name": person["bioname"].encode("utf-8"),
            "icpsr": str(person["icpsr"]).zfill(6),
            "state": state_name(person["state_abbrev"]),
            "party": party_name(person["party_code"]),
            "congress": person["congress"],
            "chamber": person["chamber"],
            "born": person.get("born", ""),
            "died": person.get("died", ""),
            "image": image,
            "source": source,
            "provenance": provenance
        }

        csv_rows.append(out_data)

    print("Found %d images total..." % len(csv_rows))
    print("Processed all images, writing output file...")

    # Sort
    csv_rows.sort(key=lambda x: (-x["congress"], x["name"]))

    # Do CSV write
    field_names = ["name", "icpsr", "state", "party", "congress",
                   "chamber", "born", "died", "image", "source",
                   "provenance"]
    with open("../members.csv", "w") as out_file:
        out_dump = csv.DictWriter(out_file, delimiter=',',
                                  quotechar='"',
                                  quoting=csv.QUOTE_NONNUMERIC,
                                  fieldnames=field_names)
        out_dump.writeheader()
        out_dump.writerows(csv_rows)

    print("OK")

def process_arguments():
    """ Handles getting the arguments from command line. """
    parser = argparse.ArgumentParser(description="Scrapes Congressional Bioguide for Bio Images")
    parser.add_argument("--type", type=str, default="mongo", nargs="?")
    arguments = parser.parse_args()

    do_dump(arguments.type)

if __name__ == "__main__":
    process_arguments()
