""" Check which congresspersons have missing images. """

from __future__ import print_function
from builtins import range
# from collections import OrderedDict
import argparse
import glob
import json
import math
import re
import traceback
import prettytable
from pymongo import MongoClient

CONFIG = {}

def party_name(party_code):
    """ Converts party code to a party name. """
    global CONFIG
    if not CONFIG or "party_data" not in CONFIG:
        CONFIG["party_data"] = json.load(open("config/parties.json", "r"))

    results = next((x for x in CONFIG["party_data"]
                    if x["party_code"] == party_code), None)
    return "Error" if results is None else results["full_name"]

def state_name(state_abbrev):
    """ Converts state abbreviation to a full name. """
    global CONFIG
    if not CONFIG or "state_data" not in CONFIG:
        CONFIG["state_data"] = json.load(open("config/states.json", "r"))

    results = next((x for x in CONFIG["state_data"]
                    if x["state_abbrev"].lower() == state_abbrev.lower()), None)
    return "Error" if results is None else results["name"]

def assemble_row(row, year):
    """ Assembles a database row into a list for prettytable. """

    bio = ""
    if "born" in row:
        bio = bio + "b. " + str(row["born"])
    if "died" in row:
        bio = bio + " d. " + str(row["died"])

    cong_year = 1789 + (row["congress"] - 1) * 2 if year else row["congress"]

    bio = bio.strip()
    return [row["bioname"], row["icpsr"],
            party_name(row["party_code"]).replace(" Party", ""),
            cong_year, state_name(row["state_abbrev"]), bio]

def image_cache():
    """ Generates an image cache. """
    local_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
                        for x in glob.glob("images/*/*.*")])
    raw_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
                      for x in glob.glob("images/raw/*/*.*")])
    images = local_images | raw_images
    return images

def mongo_query(arg_q, images):
    """ Hit Mongo DB to check who is missing. """

    # Assemble Query
    query = {"congress": {"$gt": arg_q["minc"] - 1}}
    if "maxc" in arg_q:
        query["congress"]["$lt"] = arg_q["maxc"]
    if "chamber" in arg_q:
        query["chamber"] = arg_q["chamber"]
    if "state" in arg_q:
        query["state_abbrev"] = arg_q["state"]
    if "name" in arg_q:
        name_regex = re.compile(arg_q["name"], re.IGNORECASE)
        query["bioname"] = {"$regex": name_regex}

    # Connect to DB
    print("Searching mongo database...")
    print(query)
    connection = MongoClient()
    cursor = connection["voteview"]

    # Loop over members
    seen_icpsr = []
    fields_keep = {x: 1 for x in
                   ["icpsr", "fname", "bioname", "congress",
                    "state_abbrev", "party_code", "born", "died"]}
    fields_keep["_id"] = 0

    # How to sort results
    sort_dir = -1 if "sort" in arg_q and arg_q["sort"] == "congress" else 1
    sort_query = [(arg_q["sort"], sort_dir)]

    return_set = []
    for result in (cursor.voteview_members
                   .find(query, fields_keep).sort(sort_query)):
        # Only check each ICPSR once.
        if result["icpsr"] in seen_icpsr:
            continue
        seen_icpsr.append(result["icpsr"])


        # Do we have an image?
        corrected_icpsr = str(result["icpsr"]).zfill(6)
        if corrected_icpsr in images:
            continue

        return_set.append(result)

    # How many total?
    total_number = len(cursor.voteview_members.distinct("icpsr"))

    return return_set, total_number


def flatfile_query(arg_q, images):
    """ Hit local flatfile to check who is missing. """

    print("Searching flat-file database...")
    flat_file = json.load(open("config/database-raw.json", "r"))

    def process_match(person):
        if "minc" in arg_q and person["congress"] < arg_q["minc"]:
            return False
        if "maxc" in arg_q and person["congress"] > arg_q["maxc"]:
            return False
        if "chamber" in arg_q and person["chamber"] != arg_q["chamber"]:
            return False
        if "state" in arg_q and person["state_abbrev"] != arg_q["state"]:
            return False
        if str(person["icpsr"]).zfill(6) in images:
            return False
        if ("name" in arg_q and
                arg_q["name"].lower() not in person["bioname"].lower()):
            return False
        return True

    matches = [x for x in flat_file if process_match(x)]
    sort_mult = -1 if arg_q["sort"] == "congress" else 1
    return sorted(matches,
                  key=lambda k: k[arg_q["sort"]] * sort_mult), len(flat_file)


def check_missing(args):
    """ Check who's missing from a given congress range, chamber, or state. """

    print("Beginning search...")

    # Make sure sort is a valid choice.
    if args["sort"] not in ["congress", "state_abbrev",
                            "party_code", "bioname"]:
        args["sort"] = "congress"

    i = 0

    # If user asked for year specification:
    fields = ["Name", "ICPSR", "Party", "Congress", "State", "Bio"]
    if args["year"]:
        if args["max"]:
            args["maxc"] = math.ceil((args["max"] - 1789) / float(2))

        args["minc"] = math.ceil((args["min"] - 1789) / float(2))
        fields[3] = "Year"
    else:
        args["maxc"] = args["max"]
        args["minc"] = args["min"]

    out_table = prettytable.PrettyTable(
        fields
    )

    # Cache images instead of hitting each time.
    images = image_cache()

    if args["type"] == "flat":
        missing_people, total_count = flatfile_query(args, images=images)
    else:
        missing_people, total_count = mongo_query(args, images=images)

    # Loop over results.
    for result in missing_people:
        # Add the person to our list of people who don't have images.
        i = i + 1
        try:
            row = assemble_row(result, args["year"])
            out_table.add_row(row)
        except Exception:
            print(traceback.format_exc())

    # Summary result
    if i:
        print(out_table)
        print("%d total missing from Congress %d onward" % (i, args["minc"]))
    else:
        print("OK, none missing from Congress %s onward" % (args["minc"]))

    print("Total images %d / %d" % (len(images), total_count))
    return i

def check_no_raw(suppress=0):
    """
    Check for images that we have processed versions of but not raw versions.
    """

    local_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
                        for x in glob.glob("images/*/*.*")])
    raw_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
                      for x in glob.glob("images/raw/*/*.*")])

    result = local_images - raw_images

    if result:
        print("Missing raw images:")
        if not suppress:
            print(result)
    else:
        print("OK. No missing raw images.")

    return result

def report_missing_grouped(group, db_type, sort):
    """
    Groups missing images by state or congress to see which are complete.
    """

    if group not in ["state_abbrev", "congress"]:
        group = "state_abbrev"

    if group == "state_abbrev":
        data = json.load(open("config/states.json", "r"))
        absent = [x["state_abbrev"] for x in data]
    elif group == "congress":
        absent = [x for x in range(116)][1:]

    # Load what we're missing
    images = image_cache()
    arg_query = {"minc": 1, "maxc": 0, "chamber": "", "state": "",
                 "sort": "congress"}
    if db_type == "flat":
        missing, _ = flatfile_query(arg_query, images)
    else:
        missing, _ = mongo_query(arg_query, images)

    # Iterate and group by group
    missing_group = {}
    for member in missing:
        if member[group] in missing_group:
            missing_group[member[group]] += 1
        else:
            missing_group[member[group]] = 1

    for thing in absent:
        if thing not in missing_group:
            missing_group[thing] = 0

    # Add stuff to the table
    out_table = prettytable.PrettyTable([group.title(), "Amount"])
    for key, value in missing_group.items():
        out_table.add_row([key, value])

    # Print the table
    sort = "State_Abbrev" if sort == "congress" else sort
    reversesort = True if sort == "Amount" else False
    print(out_table.get_string(sortby=sort.title(), reversesort=reversesort))

def parse_arguments():
    """ Parse command line arguments and launch the search. """
    parser = argparse.ArgumentParser(
        description="Check which congresspeople are missing."
    )
    parser.add_argument("--min", type=int, default=80, nargs="?")
    parser.add_argument("--max", type=int, default=0, nargs="?")
    parser.add_argument("--chamber", type=str, default="", nargs="?")
    parser.add_argument("--name", type=str, default="", nargs="?")
    parser.add_argument("--state", type=str, default="", nargs="?")
    parser.add_argument("--sort", type=str, default="congress", nargs="?")
    parser.add_argument("--type", type=str, default="mongo", nargs="?")
    parser.add_argument("--year", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--group", type=str, default="", nargs="?")
    arguments = parser.parse_args()

    if arguments.group:
        report_missing_grouped(arguments.group, arguments.type, arguments.sort)
        return

    elif arguments.raw:
        check_no_raw()
        return

    check_missing(vars(arguments))

if __name__ == "__main__":
    parse_arguments()
