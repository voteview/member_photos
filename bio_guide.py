""" Scrapes Congressional Bio Guide and saves images. """

import argparse
import json
import glob
import shutil
from pymongo import MongoClient
import bs4
import requests

def get_config():
	""" Reads config file and returns it. """
	config = json.load(open("config/config.json", "r"))
	return config

def list_images():
	""" Checks images subdirectory for all ICPSRs. """
	processed = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/bio_guide/*.*")])
	raw = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/raw/bio_guide/*.*")])
	return processed | raw

def get_missing(db, query):
	""" Check which ICPSRs in our query are actually missing. """
	present_set = list_images()
	person_set = []
	icpsr_set = []
	for row in db.voteview_members.find(query, {"bioguide_id": 1, "bioname": 1, "congress": 1, "icpsr": 1}, no_cursor_timeout=True):
		# Because same ICPSR can be recycled, keep a running list of viewed ICPSRs
		if row.get("icpsr", 0) not in icpsr_set:
			new_entry = [str(row["icpsr"]).zfill(6), row["bioguide_id"]]
			person_set.append(new_entry)
			icpsr_set.append(row["icpsr"])

	icpsr_zfill = set([x[0] for x in person_set])
	missing = icpsr_zfill - present_set

	return [x for x in person_set if x[0] in missing]

def save_image(icpsr, extension, data):
	""" Simple helper to do a binary file write. """
	with open("images/raw/bio_guide/" + icpsr + "." + extension, "wb") as out_file:
		shutil.copyfileobj(data, out_file)

def main_loop(query):
	""" Get missing members and scrape a photo for each of them from the bio guide. """

	# Connect
	config = get_config()
	connection = MongoClient()
	db = connection["voteview"]
	lookup_url = config["bio_guide_url"]

	# Get missing
	missing_icpsrs = get_missing(db, query)

	# Iterate through the set.
	i = 0
	for person in missing_icpsrs:
		# Expand, print
		icpsr, bioguide_id = person
		print("Lookup for icpsr %s (bio guide ID %s)... %d/%d" % (icpsr, bioguide_id, i, len(missing_icpsrs)))

		# Load congress bio page
		page_request = requests.get(lookup_url + bioguide_id).text
		parser = bs4.BeautifulSoup(page_request, "html.parser")

		# List images on page and extract
		images = parser.find_all("img")[1:]
		if len(images):
			print("\t Found image!")
			extension = images[0]["src"].split(".")[-1]
			url = "http:" + images[0]["src"]
			binary_download = requests.get(url, stream=True)
			save_image(icpsr, extension, binary_download.raw)
			print("\t OK, downloaded!")
		else:
			print("\t No image")

		i = i + 1

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Scrapes Congressional Bioguide for Bio Images")
	parser.add_argument("congress", type=int, nargs="?", default=105)
	arguments = parser.parse_args()

	main_loop({"bioguide_id": {"$exists": True}, "congress": {"$gt": arguments.congress}})

