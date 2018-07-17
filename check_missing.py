""" Check which congresspersons have missing images. """

import argparse
import glob
import prettytable
from pymongo import MongoClient
import traceback
import sys

sys.path.append('/var/www/voteview/')
from model.searchParties import partyName
from model.stateHelper import stateName

def assemble_row(row):
	""" Assembles a database row into a list for prettytable. """

	bio = ""
	if "born" in row:
		bio = bio + "b. " + str(row["born"])
	if "died" in row:
		bio = bio + " d. " + str(row["died"])
		
	bio = bio.strip()
	return [row["bioname"], row["icpsr"], partyName(row["party_code"]).replace(" Party", ""), row["congress"], stateName(row["state_abbrev"]), bio]


def check_missing(minimum_congress, chamber, state):
	""" Check who's missing from a given congress range, chamber, or state. """

	# Assemble Query
	query = {"congress": {"$gt": minimum_congress - 1}}
	if len(chamber):
		query["chamber"] = chamber
	if len(state):
		query["state_abbrev"] = state

	print("Beginning search...")
	print(query)

	i = 0
	out_table = prettytable.PrettyTable(["Name", "ICPSR", "Party", "Congress", "State", "Bio"])

	# Cache images instead of hitting each time.
	site_images = [x.rsplit("/", 1)[1].split(".", 1)[0] for x in glob.glob("/var/www/voteview/static/img/bios/*.*")]
	local_images = [x.rsplit("/", 1)[1].split(".", 1)[0] for x in glob.glob("images/*/*.*")]
	images = site_images + local_images

	# Connect to DB
	connection = MongoClient()
	db = connection["voteview"]

	# Loop over members	
	seen_icpsr = []
	fields_keep = {x: 1 for x in ["icpsr", "fname", "bioname", "congress", "state_abbrev", "party_code", "born", "died"]}
	fields_keep["_id"] = 0
	for result in db.voteview_members.find(query, fields_keep).sort([("congress", -1)]):
		# Only check each ICPSR once.
		if result["icpsr"] in seen_icpsr:
			continue
		seen_icpsr.append(result["icpsr"])

		
		# Do we have an image?
		corrected_icpsr = str(result["icpsr"]).zfill(6)
		if corrected_icpsr in images:
			continue
	
			
		# Add the person to our list of people who don't have images.
		i = i + 1
		try:
			row = assemble_row(result)
			out_table.add_row(row)
		except:
			print traceback.format_exc()
			pass

	# Summary result
	if i:
		print(out_table)
		print("%d total missing from Congress %d onward" % (i, minimum_congress))
	else:
		print("OK, none missing from Congress %s onward" % (minimum_congress))

if __name__=="__main__":
	parser = argparse.ArgumentParser(description = "Check which congresspeople are missing.")
	parser.add_argument("min", type=int, default=90, nargs="?")
	parser.add_argument("chamber", type=str, default="", nargs="?")
	parser.add_argument("state", type=str, default="", nargs="?")
	arguments = parser.parse_args()

	check_missing(arguments.min, arguments.chamber, arguments.state)
