""" Check which congresspersons have missing images. """

from __future__ import print_function
import argparse
import glob
import json
import prettytable
import sys
import traceback
from pymongo import MongoClient

CONFIG = {}

def party_name(party_code):
	""" Converts party code to a party name. """
	global CONFIG
	if not CONFIG or not "party_data" in CONFIG:
		CONFIG["party_data"] = json.load(open("config/parties.json", "r"))

	results = next((x for x in CONFIG["party_data"] if x["party_code"] == party_code), None)
	return "Error" if results is None else results["full_name"]

def state_name(state_abbrev):
	""" Converts state abbreviation to a full name. """
	global CONFIG
	if not CONFIG or not "state_data" in CONFIG:
		CONFIG["state_data"] = json.load(open("config/states.json", "r"))

	results = next((x for x in CONFIG["state_data"] if x["state_abbrev"].lower() == state_abbrev.lower()), None)
	return "Error" if results is None else results["name"]

def assemble_row(row):
	""" Assembles a database row into a list for prettytable. """

	bio = ""
	if "born" in row:
		bio = bio + "b. " + str(row["born"])
	if "died" in row:
		bio = bio + " d. " + str(row["died"])

	bio = bio.strip()
	return [row["bioname"], row["icpsr"],
		party_name(row["party_code"]).replace(" Party", ""),
		row["congress"], state_name(row["state_abbrev"]), bio]

def image_cache():
	""" Generates an image cache. """
	local_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
		for x in glob.glob("images/*/*.*")])
	raw_images = set([x.rsplit("/", 1)[1].split(".", 1)[0]
		for x in glob.glob("images/raw/*/*.*")])
	images = local_images | raw_images
	return images

def mongo_query(minimum_congress, chamber, state, sort, images):
	""" Hit Mongo DB to check who is missing. """

	# Assemble Query
	query = {"congress": {"$gt": minimum_congress - 1}}
	if len(chamber):
		query["chamber"] = chamber
	if len(state):
		query["state_abbrev"] = state

	# Connect to DB
	print("Searching mongo database...")
	connection = MongoClient()
	cursor = connection["voteview"]

	# Loop over members
	seen_icpsr = []
	fields_keep = {x: 1 for x in
		["icpsr", "fname", "bioname", "congress",
		"state_abbrev", "party_code", "born", "died"]}
	fields_keep["_id"] = 0

	# How to sort results
	sort_dir = -1 if sort == "congress" else 1
	sort_query = [(sort, sort_dir)]

	return_set = []
	for result in cursor.voteview_members.find(query, fields_keep).sort(
		sort_query
	):
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


def flatfile_query(minimum_congress, chamber, state, sort, images):
	""" Hit local flatfile to check who is missing. """

	print("Searching flat-file database...")
	flat_file = json.load(open("config/database-raw.json", "r"))

	def process_match(x):
		if minimum_congress and x["congress"] < minimum_congress:
			return False
		if chamber and x["chamber"] != chamber:
			return False
		if state and x["state_abbrev"] != state:
			return False
		if str(x["icpsr"]).zfill(6) in images:
			return False
		return True

	matches = [x for x in flat_file if process_match(x)]
	sort_mult = -1 if sort == "congress" else 1
	return sorted(matches, key=lambda k: k[sort] * sort_mult), len(flat_file)


def check_missing(minimum_congress, chamber, state, sort, query_type):
	""" Check who's missing from a given congress range, chamber, or state. """

	print("Beginning search...")

	# Make sure sort is a valid choice.
	if sort not in ["congress", "state_abbrev", "party_code", "bioname"]:
		sort = "congress"

	i = 0
	out_table = prettytable.PrettyTable(
		["Name", "ICPSR", "Party", "Congress", "State", "Bio"]
	)

	# Cache images instead of hitting each time.
	images = image_cache()

	if query_type == "flat":
		missing_people, total_count = flatfile_query(minimum_congress, chamber, state, sort, images)
	else:
		missing_people, total_count = mongo_query(minimum_congress, chamber, state, sort, images)

	# Loop over results.
	for result in missing_people:
		# Add the person to our list of people who don't have images.
		i = i + 1
		try:
			row = assemble_row(result)
			out_table.add_row(row)
		except:
			print(traceback.format_exc())

	# Summary result
	if i:
		print(out_table)
		print("%d total missing from Congress %d onward" % (i, minimum_congress))
	else:
		print("OK, none missing from Congress %s onward" % (minimum_congress))

	print("Total images %d / %d" % (len(images), total_count))

def parse_arguments():
	""" Parse command line arguments and launch the search. """
	parser = argparse.ArgumentParser(
		description="Check which congresspeople are missing."
	)
	parser.add_argument("--min", type=int, default=90, nargs="?")
	parser.add_argument("--chamber", type=str, default="", nargs="?")
	parser.add_argument("--state", type=str, default="", nargs="?")
	parser.add_argument("--sort", type=str, default="congress", nargs="?")
	parser.add_argument("--type", type=str, default="mongo", nargs="?")
	arguments = parser.parse_args()

	check_missing(arguments.min, arguments.chamber, arguments.state, arguments.sort, arguments.type)

if __name__ == "__main__":
	parse_arguments()
