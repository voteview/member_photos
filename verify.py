""" Tests integrity of output. """

from __future__ import print_function
import csv
import glob
import json
import os
import sys
import traceback
from check_missing import check_missing, check_no_raw

def verify():
	""" Verify sanity of data. """

	# Check missing images since 1947 -- should be zero.
	arguments = {"min": 80, "max": 0, "chamber": "", "name": "", "state": "", "sort": "congress", "type": "flat", "year": False, "raw": False, "group": ""}
	number_missing_current = check_missing(arguments)

	# Check missing raw images
	number_missing_raw = check_no_raw()

	# Check that everyone in the members file has a photo and every photo has an entry in the members file.
	all_exposed_photos = set(glob.glob("images/bio_guide/*")) | set(glob.glob("images/wiki/*")) | set(glob.glob("images/manual/*"))

	# Check integrity of provenance file.
	try:
		_ = json.load(open("config/provenance.json", "r"))
	except:
		print("Data integrity error: Invalid provenance file")
		print(traceback.format_exc())
		sys.exit(1)

	# Try to load member csv
	error = 0
	try:
		# Read the member CSV and get members -- also checks CSV integrity
		with open("members.csv", "r") as member_csv:
			member_reader = csv.reader(member_csv, delimiter=",", quotechar='"')
			members = [x for x in member_reader][1:]

		# Isolate images claimed
		images = set([x[-3] for x in members])

		# How many unknown provenance
		unknown_provenance = [x for x in members if x[-1] == "Unknown Provenance [!]"]

		# How many do we have files but not entries for?
		diff_set = all_exposed_photos - images

		# How many do we have entries but not files for?
		photos_missing = images - all_exposed_photos
	except:
		print(traceback.format_exc())
		error = 1

	if error:
		print("Error reading CSV file.")
		sys.exit(1)

	if number_missing_current or number_missing_raw or len(diff_set) or len(photos_missing) or len(unknown_provenance) > 4:
		print("We have one or more data integrity issues.")

		if number_missing_current:
			print("Missing %d images for modern congressmen." % number_missing_current)
		if number_missing_raw:
			print("Missing %d raw images for represented final images." % number_missing_raw)
		if len(diff_set):
			print("Some images we possess are not represented in members file.")
			print(diff_set)
		if len(photos_missing):
			print("Some images in the members file are not in our possession.")
			print(list(photos_missing)[0:10])
		if len(unknown_provenance) > 4:
			print("Some members have no provenance statement for their image.")
			print(unknown_provenance)

		sys.exit(1)

if __name__ == "__main__":
	verify()
