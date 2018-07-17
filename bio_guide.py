""" Scrapes Congressional Bio Guide and saves images. """

import glob
import requests
import shutil
import argparse
from pymongo import MongoClient
import bs4

def has_image(icpsr):
	""" Checks images subdirectory for this ICPSR. """
	return len(glob.glob("bio_guide_images/" + icpsr + ".*"))

def get_missing(db, query):
	person_set = []
	icpsr_set = []
	for r in db.voteview_members.find(query, {"bioguide_id": 1, "bioname": 1, "congress": 1, "icpsr": 1}, no_cursor_timeout = True):
		if r.get("icpsr", 0) not in icpsr_set:
			new_entry = [str(r["icpsr"]).zfill(6), r["bioguide_id"]]
			person_set.append(new_entry)
			icpsr_set.append(r["icpsr"])

	return [x for x in person_set if not has_image(x[0])]

def save_image(icpsr, extension, data):
	with open("bio_guide_images/" + icpsr + "." + extension, "wb") as out_file:
		shutil.copyfileobj(data, out_file)

def main_loop(query):
	connection = MongoClient()
	db = connection["voteview"]
	lookup_url = "http://bioguide.congress.gov/scripts/biodisplay.pl?index="
	
	missing_icpsrs = get_missing(db, query)

	i = 0
	for person in missing_icpsrs:
		icpsr, bioguide_id = person
		print("Lookup for icpsr %s (bio guide ID %s)... %d/%d" % (icpsr, bioguide_id, i, len(missing_icpsrs)))
		
		# Load congress bio page
		page_request = requests.get(lookup_url + bioguide_id).text
		parser = bs4.BeautifulSoup(page_request, "html5lib")

		# List images on page and extract
		images = parser.find_all("img")[1:]
		if len(images):
			print("\t Found image!")
			extension = images[0]["src"].split(".")[-1]
			url = "http:" + images[0]["src"]
			binary_download = requests.get(url, stream = True)
			save_image(icpsr, extension, binary_download.raw)
			print("\t OK, downloaded!")
		else:
			print("\t No image")

		i = i + 1

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Scrapes Congressional Bioguide for Bio Images")
	parser.add_argument("congress", type=int, nargs="?", default=70)
	arguments = parser.parse_args()

	main_loop({"bioguide_id": {"$exists": True}, "congress": {"$gt": arguments.congress}})

