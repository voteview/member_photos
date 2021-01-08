""" Check which congresspersons have missing images. """

from __future__ import print_function
import json
from pymongo import MongoClient

def get_config():
    """ Reads config file and returns it. """
    config = json.load(open("config.json", "r"))
    return config

def do_dump():
    """ Dumps the database to ready the scrapers for flat-file support. """

    config = get_config()
    connection = MongoClient(config["db_host"], config["db_port"])
    cursor = connection["voteview"]

    fields_keep = {x: 1 for x in
                   ["icpsr", "fname", "bioname", "congress", "chamber",
                    "state_abbrev", "party_code", "born", "died",
                    "bioguide_id"]}
    fields_keep["_id"] = 0

    seen_icpsr = []
    results = []
    for result in (cursor.voteview_members.find({}, fields_keep)
                   .sort([("congress", -1)])):
        if result["icpsr"] in seen_icpsr:
            continue
        seen_icpsr.append(result["icpsr"])
        results.append(result)

    with open("database-raw.json", "w") as out_file:
        json.dump(results, out_file)

if __name__ == "__main__":
    do_dump()
