from __future__ import print_function

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
import traceback
import requests
import pymongo
from requests.packages import urllib3
urllib3.disable_warnings()

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

def try_download(search_object, tries, filename, config):
	""" Takes an image URL and disambiguates and downloads the image matching the search. """

	headers = {"User-Agent": config["user_agent"]}

	# Removing a bunch of fluff Wikipedia adds to file names.
	fluff_strip = ["Image:", "File:", "image:", "file:"]
	for strip in fluff_strip:
		filename = filename.replace(strip, "")

	if filename.startswith("[["):
		filename = filename.split("[[", 1)[1].split("]]", 1)[0]

	for x in ["|", "{{", "<!--"]:
		if x in filename:
			filename = filename.split(x, 1)[0]

	# Make sure what's left is a filename
	if not filename.strip():
		print("  " * tries, "Not actually a real image.")
		return -1

	# Make the request to get the final URL from the Wikipedia API
	print("  " * tries, "Image filename: %s. Beginning download." % filename)
	req_params = {"action": "query", "prop": "imageinfo", "iiprop": "url", "format": "json", "titles": "File:" + filename}
	result = requests.get("http://en.wikipedia.org/w/api.php", params = req_params, headers = headers).json()

	# We found it, now download it
	if "query" in result and "pages" in result["query"]:
		# Extract URL
		key_index = result["query"]["pages"].keys()[0]
		image_final_url = result["query"]["pages"][key_index]["imageinfo"][0]["url"]
		print("  " * tries, "Modified filename: %s. And now actual download." % image_final_url)

		# Prep filename and get data
		extension = image_final_url.split(".")[-1]
		padded_icpsr = str(search_object["icpsr"]).zfill(6)
		data = requests.get(image_final_url, stream=True, headers = headers)

		# Create output directory if it doesn't exist
		final_dir = os.path.dirname("images/raw/wiki/")
		if not os.path.exists(final_dir):
			os.makedirs(final_dir)

		# Now write the data
		with open("images/raw/wiki/" + padded_icpsr + "." + extension, "wb") as output_file:
			shutil.copyfileobj(data.raw, output_file)

		print("  " * tries, "Download OK, saved as images/raw/wiki/%s.%s" % (padded_icpsr, extension))
		return 1

	return -1

def get_saved_results():
	""" Reads Wikipedia search saved results to avoid duplicating. """
	return json.load(open("config/wiki_results.json", "r"))

def get_current_images():
	""" Return the currently available images. """

	bio_guide = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/bio_guide/*.*")])
	wiki = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/wiki/*.*")])
	bio_guide_raw = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/raw/bio_guide/*.*")])
	wiki_raw = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/raw/wiki/*.*")])

	return bio_guide | wiki | bio_guide_raw | wiki_raw

def get_config():
	""" Read config JSON file and return it. """
	return json.load(open("config/config.json", "r"))

def score_text(text, search_object):
	""" Score biographical text to see how well it matches our search. """
	score = 0

	# Generic biographical match
	if any([x in text.lower() for x in ["politician", "representative", "senator", "house of", "legislator"]]):
		score = score + 1
	if "america" in text.lower():
		score = score + 1

	# Specific match
	if state_name(search_object["state_abbrev"]).lower() in text.lower():
		score = score + 1
	if search_object["search_party_name"].lower() in text.lower():
		score = score + 1
	if "born" in search_object and str(search_object["born"]) in text.lower():
		score = score + 1
	if "died" in search_object and str(search_object["died"]) in text.lower():
		score = score + 1

	return score

def search_member(search_object, config, tries = 1):
	if tries > 10:
		return -1

	# Load config and set up request
	config = get_config()
	wiki_url = config["wiki_base_search_url"]
	headers = {"User-Agent": config["user_agent"]}

	# Request
	result = json.loads(requests.get(wiki_url + search_object["fixed_name"], headers=headers).text)

	# Check to see if the result is sane.
	if "query" in result and "pages" in result["query"]:
		if len(result["query"]["pages"]) != 1:
			print("  " * tries, "Error: Number of results was not 1. Instead, it was %d" % (len(result["query"]["pages"])))
			return
	else:
		return found_no_results(search_object, config)

	# If we didn't find an actual page.
	if result["query"]["pages"].keys()[0] == "-1":
		print("  " * tries, "Error: No results found from search.")
		return found_no_results(search_object, config)

	# Get the page object: pages is a named dict but we've verified it only has one item, so we take that item.
	page = result["query"]["pages"].values()[0]

	if "*" in page["revisions"][0]:
		page_text = page["revisions"][0]["*"]
	else:
		page_text = ""

	# Check for redirects:
	if page_text.lower().startswith("#redirect"):
		return handle_redirect(search_object, page_text, config, tries)

	# Check for name disambiguations.
	try_also = []
	if any([page_text.strip().lower().startswith(x) for x in ["{{about-otherpeople", "{{about", "{{for"]]):
		about_spelling = re.search("(\{\{(about(-otherpeople)?|for))", page_text, flags=re.IGNORECASE).groups(1)[0]

		# This is not quite right: could have embedded {{}} but going to assume for now.
		possible_disambiguation = page_text.strip().split(about_spelling + "|", 1)[1].split("}}", 1)[0].split("|")

		# The options here are either {{About|current article}} or {{About|current article|other descriptor|other article link|...}}
		# if we have more than one, skip. Also skip "ands"
		if len(possible_disambiguation) > 1:
			possible_disambiguation = [x.strip() for x in possible_disambiguation[1:] if x.strip().lower() != "and"]

		max_score = -1
		right_choice = ""
		for choice in possible_disambiguation:
			score = score_text(choice, search_object)
			if score > max_score:
				max_score = score
				right_choice = choice

		try_also.append(right_choice)


	# This page is a person, but there's a disambiguation page for the person as well.
	if any([page_text.strip().lower().startswith(x) for x in ["{{other people", "{{other uses"]]):
		print("  " * tries, "Found a top inline disambiguation page. Searching.")
		result = handle_inline_redirect(search_object, page_text, config, tries)
		if len(result):
			print("  " * tries, "%s is best reserve result if current page is wrong" % result)
			try_also.append(result)

	# Junior
	if search_object["is_junior"]:
		try_also.append(search_object["fixed_name"] + " Jr.")

	# This page is explicitly a disambiguation page.
	if "may refer to" in page_text.lower() or "may also refer to" in page_text.lower() or "{{hndis|" in page_text.lower():
		search_object["fixed_name"] = disambiguate(search_object, page_text, config, tries)
		return search_member(search_object, config, tries + 1)

	# At this point we are reasonably certain that we're on the right page. Let's score to be sure.
	score = score_text(page_text, search_object)
	if score < 3:
		print("  " * tries, "We believe we are on the right page, but it's not right. Score was: %d" % score)
		if not len(try_also):
			return -1

		print("  " * tries, "Trying top disambiguation %s." % try_also[0])
		search_object["fixed_name"] = try_also[0]
		return search_member(search_object, config, tries + 1)

	# Now look for photo.
	found = 0

	# Ideally, they have an info box with a photo.
	if re.search("\{\{\s*(Infobox|officeholder)", page_text, flags = re.IGNORECASE):
		matches = re.search("(\{\{\s*(Infobox|officeholder))", page_text, flags = re.IGNORECASE)
		info_box_lines = page_text.split(matches.groups(1)[0], 1)[1].split("}}", 1)[0].split("\n")
		priority_set = [["image", "image name"], ["smallimage"]]
		for current_set in priority_set:
			for line in info_box_lines:
				if "=" not in line:
					continue

				line = line.strip().split("|", 1)[1]

				key, value = line.split("=", 1)
				if key.strip() in current_set and len(value.strip()):
					found = 1
					photo_guess = value.strip()
					break

			if found:
				break


	# If not, perhaps they have an inline photo.
	if found == 0 and "[[Image:" in page_text:
		found = 1
		photo_guess = page_text.split("[[Image:", 1)[1].split("]]")[0]

	if found == 0 and "[[File:" in page_text:
		found = 1
		photo_guess = page_text.split("[[File:", 1)[1].split("]]")[0]

	if found and "{{#Property" in photo_guess:
		photo_guess = get_property_image(search_object, tries, photo_guess, config)

	if found and photo_guess.strip().startswith("<!--"):
		print("  " * tries, "Apparent photo is actually just a comment.")
		found = 0

	if found:
		print("  " * tries, "Photo URL? ", photo_guess)
		return try_download(search_object, tries, photo_guess, config)

	print("  " * tries, "No photo found.")
	return 0

def get_property_image(search_object, tries, photo_guess, config):
	""" Pulls from the separate image API. """

	# Make request
	headers = {"User-Agent": config["user_agent"]}
	base_url = "http://en.wikipedia.org/w/api.php?action=query&prop=images&format=json&titles="
	result = requests.get(base_url + search_object["fixed_name"]).json()

	# Extract result
	page_key = result["query"]["pages"].keys()[0]
	return result["query"]["pages"][page_key]["images"][0]["title"]

def found_no_results(search_object, config, tries = 1):
	""" Try fixing some common name causes of having no results. """
	print("  " * tries, "Error: Found no search results. Checking alternate options.")

	# Mc prefix in family name? Need to fix capitalization.
	if any(x in search_object["fixed_name"] for x in [" Mc", " Mac"]):
		first, family = search_object["fixed_name"].rsplit(" ", 1)
		for chunk in ["Mc", "Mac"]:
			if family.startswith(chunk):
				new_name = first + " " + chunk + family[len(chunk)].upper() + family[len(chunk) + 1:]
				if new_name == search_object["fixed_name"]:
					break

				print("  " * tries, "Name contains '%s' prefix, possible capitalization issue. Trying again with new name %s." % (chunk, new_name))
				search_object["fixed_name"] = new_name
				return search_member(search_object, config, tries + 1)

	# Superfluous middle name
	if len(search_object["fixed_name"].split(" ")) > 2:
		# Use original name to build derivative searches
		original_name = search_object["fixed_name"]

		# First Last
		search_object["fixed_name"] = original_name.split(" ")[0] + " " + original_name.rsplit(" ", 1)[1]
		print("  " * tries, "Trying to drop middle name. New search name: %s" % search_object["fixed_name"])
		result = search_member(search_object, config, tries + 1)

		if result != -1:
			return result

		# Middle Last: remove () from middle name if it's a nickname
		middle = original_name.split(" ")[1].replace("(", "").replace(")", "")
		search_object["fixed_name"] = middle + " " + original_name.rsplit(" ", 1)[1]
		print("  " * tries, "Searching with middle + last. New search name: %s" % search_object["fixed_name"])
		return search_member(search_object, config, tries + 1)

	print("  " * tries, "Error: No remaining alternate options.")
	return -1

def build_object(member, tries=1):
	""" Adds additional metadata to member object for searching. """

	if "bioname" not in member:
		print("  " * tries, "Error: no full name.")
		raise ValueError
		return

	# Set up some additional search metadata
	search_object = dict(member)
	# Re-arranging names
	# Flag for junior
	if member["bioname"].lower().endswith(", jr.") or member["bioname"].lower().endswith(" jr."):
		search_object["is_junior"] = 1
		new_bioname = re.sub(",? jr.?", "", member["bioname"], flags=re.IGNORECASE)
		search_object["fixed_name"] = " ".join((new_bioname.split(", ")[1] + " " + new_bioname.split(", ")[0]).title().split())
	else:
		search_object["is_junior"] = 0
		search_object["fixed_name"] = " ".join((member["bioname"].split(", ")[1] + " " + member["bioname"].split(", ")[0]).title().split())
	# Party name:
	try:
		search_object["search_party_name"] = party_name(member["party_code"])
	except:
		pass

	return search_object

def handle_redirect(search_object, text, config, tries):
	""" Extracts the redirect and calls the search again. """
	redirect_name = text.split("[[", 1)[1].split("]]", 1)[0]
	if "|" in redirect_name:
		redirect_name = redirect_name.split("|", 1)[0]

	search_object["fixed_name"] = redirect_name
	print("  " * tries, "Hit redirect. Changing search name to: ", redirect_name)
	return search_member(search_object, config, tries + 1)

def handle_inline_redirect(search_object, page_text, config, tries):
	""" Read the inline redirect disambiguation page and return the best result of the bunch. """

	# Load config and set up request
	config = get_config()
	wiki_url = config["wiki_base_search_url"]
	headers = {"User-Agent": config["user_agent"]}

	# Request
	other_people_spelling = re.search("(\{\{(other people|other uses))", page_text, flags=re.IGNORECASE).groups(1)[0]
	try:
		other_people_name = page_text.split(other_people_spelling, 1)[1].split("}}", 1)[0].split("|")[1] + " (disambiguation)"
	except:
		other_people_name = search_object["fixed_name"] + " (disambiguation)"

	print(other_people_name)

	result = json.loads(requests.get(wiki_url + other_people_name, headers=headers).text)

	try:
		page_text = result["query"]["pages"].values()[0]["revisions"][0]["*"]
	except:
		return ""

	page = result["query"]["pages"].values()[0]

	if "*" in page["revisions"][0]:
		page_text = page["revisions"][0]["*"]
	else:
		page_text = ""

	return disambiguate(search_object, page_text, config, tries)

def disambiguate(search_object, page_text, config, tries):
	""" Handles formal disambiguation pages by finding best result and returning it. """

	print("  " * tries, "Name is ambiguous. Got a result, but it is a disambiguation page.")
	name_choices = [x.split("\n")[0].strip() for x in page_text.split("\n*")[1:]]
	print("  " * tries, "%d possible choices of page." % len(name_choices))
	max_score = -1
	right_choice = ""
	for choice in name_choices:
		score = score_text(choice, search_object)
		if score > max_score and choice.split("[[", 1)[1].split("]]")[0].lower() != search_object["fixed_name"].lower():
			max_score = score
			right_choice = choice

	if not len(right_choice):
		return ""

	new_name = right_choice.split("[[", 1)[1].split("]]")[0]
	if "|" in new_name:
		new_name = new_name.split("|", 1)[0]

	print("  " * tries, "Best choice %s" % new_name)
	return new_name

def single_scrape(icpsr, url):
	# Load config and set up request
	config = get_config()
	wiki_url = config["wiki_base_search_url"]
	headers = {"User-Agent": config["user_agent"]}

	# What do we begin with?
	have_images = get_current_images()
	saved_results = get_saved_results()
	padded_icpsr = str(icpsr).zfill(6)

	# Make sure we can actually run this query.
	if padded_icpsr in have_images:
		print("We already have an image for ICPSR %d" % icpsr)
		return

	if padded_icpsr in saved_results["blacklist"]:
		print("ICPSR %d is explicitly blacklisted." % icpsr)
		return

	# DB connection
	connection = pymongo.MongoClient()
	db = connection["voteview"]

	# Which fields we want to keep
	keep_fields = {x: 1 for x in ["bioname", "congress", "icpsr", "party_code", "state_abbrev", "born", "died"]}
	keep_fields["_id"] = 0

	member = db.voteview_members.find_one({"icpsr": icpsr})
	if not member:
		print("Error finding ICPSR %d in database" % icpsr)
		return

	# Okay, now build query.
	search = build_object(member)
	search["fixed_name"] = url.rsplit("/", 1)[1].replace("_", " ")

	result = search_member(search, config, tries = 1)
	if result == 0:
		print("URL provided does not have a valid image for ICPSR %d" % icpsr)

	if result == -1:
		print("Error finding suitable page for ICPSR %d" % icpsr)

def db_scrape(congress_min, congress_max, resume, max_items):
	""" Get members from the database that are missing and scrape them. """

	# Load config and set up request
	config = get_config()
	wiki_url = config["wiki_base_search_url"]
	headers = {"User-Agent": config["user_agent"]}

	# What do we begin with?
	have_images = get_current_images()
	saved_results = get_saved_results()
	need_images = []
	seen_icpsr = []

	connection = pymongo.MongoClient()
	db = connection["voteview"]
	db.voteview_members.ensure_index([("icpsr", pymongo.ASCENDING)])

	query = {"congress": {"$gte": congress_min, "$lte": congress_max}}
	keep_fields = {x: 1 for x in ["bioname", "congress", "icpsr", "party_code", "state_abbrev", "born", "died"]}
	keep_fields["_id"] = 0

	print("Beginning database query to load ICPSRs of interest...")
	expiry_date = int(datetime.datetime.now().strftime("%s")) - (7 * 24 * 60 * 60)
	for result in db.voteview_members.find(query, keep_fields, no_cursor_timeout=True).sort([("icpsr", 1)]):
		# Make sure we have only seen each ICPSR one time
		if result["icpsr"] in seen_icpsr:
			continue
		seen_icpsr.append(result["icpsr"])

		# Make sure we don't search for people we have images for.
		padded_icpsr = str(result["icpsr"]).zfill(6)
		if padded_icpsr in have_images:
			continue

		# Check to see if this ICPSR is on our blacklist.
		if padded_icpsr in saved_results["blacklist"]:
			continue

		# Check if we've already checked this article recently.
		if padded_icpsr in saved_results["greylist"].keys() and expiry_date < int(saved_results["greylist"][padded_icpsr]):
			continue

		need_images.append(result)

	print("%d members found who need images..." % len(need_images))
	max_items = max_items or len(need_images)

	# Now actually do the remote searches
	i = 0
	failed_searches = []
	no_photos = []
	for member in need_images:
		try:
			print("Searching for member %s %s..." % (str(member["icpsr"]).zfill(6), member["bioname"]))
			search = build_object(member)

			result = search_member(search, config, tries = 1)
			if result == 0:
				no_photos.append(search)

			if result < 0:
				failed_searches.append([search["icpsr"], search["fixed_name"], search["state_abbrev"], search["party_code"]])

			i = i + 1
			if i > max_items:
				break
		except:
			print("Failed while searching for member.")
			print(traceback.format_exc())

	if len(no_photos):
		handle_null_results(no_photos)

	print("\n\n====\n", "Search complete. Failed searches %d / %d " % (len(failed_searches), i))
	print(failed_searches)

def handle_null_results(which_failed):
	""" Writes a grey-list of articles that were examined, are the right people, but don't have photos. """

	# Read current greylist, add a new greylist
	existing_wiki = json.load(open("config/wiki_results.json", "r"))
	new_fails = {str(k["icpsr"]).zfill(6): datetime.datetime.now().strftime("%s") for k in which_failed}
	existing_wiki["greylist"].update(new_fails)

	# Write to the file for next time.
	with open("config/wiki_results.json", "w") as out_file:
		json.dump(existing_wiki, out_file)

def blacklist_icpsr(icpsr):
	""" Adds ICPSRs to the blacklist. """

	# Load existing blacklist
	existing_wiki = json.load(open("config/wiki_results.json", "r"))
	blacklist = set(existing_wiki["blacklist"])

	# Prep new one
	new_blacklist = set([str(x).zfill(6) for x in icpsr if x])
	existing_wiki["blacklist"] = list(blacklist | new_blacklist)

	# Write it out
	with open("config/wiki_results.json", "w") as out_file:
		json.dump(existing_wiki, out_file)

	print("Added %d ICPSRs to blacklist" % len(icpsr))

def parse_arguments():
	""" Parses command line arguments and launches search. """
	parser = argparse.ArgumentParser(description = "Scrape Wikipedia for congressional photos.")
	parser.add_argument("--min", type=int, default=20, nargs="?")
	parser.add_argument("--max", type=int, default=200, nargs="?")
	parser.add_argument("--resume", type=int, default=0, nargs="?")
	parser.add_argument("--icpsr", type=int, default=0, nargs=1)
	parser.add_argument("--url", type=str, default="", nargs=1)
	parser.add_argument("--max_items", type=int, default=0, nargs="?")
	parser.add_argument("--blacklist", type=int, default=0, nargs="*")
	arguments = parser.parse_args()

	if arguments.blacklist:
		blacklist_icpsr(arguments.blacklist)
	elif len(arguments.url) and len(arguments.icpsr):
		single_scrape(arguments.icpsr[0], arguments.url[0])
	else:
		db_scrape(arguments.min, arguments.max, arguments.resume, arguments.max_items)

if __name__ == "__main__":
	parse_arguments()
