# Works for updated schema.
import argparse
import glob
import json
import codecs
import requests
import os
from fuzzywuzzy import fuzz
import shutil
import pymongo
import sys
import re
import bs4
import traceback
sys.path.append('/var/www/voteview/')
from model.searchParties import partyName
from model.stateHelper import stateName
from urllib import quote_plus
requests.packages.urllib3.disable_warnings()
connection = pymongo.MongoClient()  
db = connection["voteview"]

def mapPhoto(filename):
	
	
	if filename.startswith("[["):
		filename = filename.split("[[",1)[1].split("]]",1)[0].split("|",1)[0]
	if "|" in filename:
		print "de piped"
		filename = filename.split("|",1)[0]
	if "Image:" in filename:
		filename = filename.replace("Image:","")
	if "File:" in filename:
		filename = filename.replace("File:","")
	if "file: " in filename:
		filename = filename.replace("file:","")
	if "image:" in filename:
		filename = filename.replace("image:","")
	if "#Property" in filename:
		return "INVALID IMAGE CAN'T DOWNLOAD"		
	if "|" in filename:
		print "how is this possible?"
		print filename
	if "{{" in filename:
		filename = filename.split("{{",1)[0]

	try:
		filename = quote_plus(filename)
	except:
		return "INVALID IMAGE CAN'T DOWNLOAD"
	photoURL = "http://en.wikipedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url&format=json&titles=File:"
	print photoURL+filename
	result = json.loads(requests.get(photoURL+filename,headers=headers).text)	
	for page in result["query"]["pages"]:
		try:
			url = result["query"]["pages"][page]["imageinfo"][0]["url"]
			doDownload(url, res["icpsr"])
			return url
		except:
			print traceback.format_exc()
			return "INVALID IMAGE CAN'T DOWNLOAD"

def doDownload(url, icpsr):
	ext = url.split(".")[-1]
	icpsrPad = str(icpsr).zfill(6)
	r = requests.get(url, stream=True, headers=headers)
	with open("wiki/images/"+icpsrPad+"."+ext,"wb") as of:
		shutil.copyfileobj(r.raw, of)
	print "DL OK"

def writeGuess(icpsrName, wikiPage, photoFile, icpsr):
	db.voteview_members.update({'icpsr': icpsr}, {'$set': {'wiki': wikiPage, 'wiki_status': 0}}, upsert=False, multi=True)

	with codecs.open("wiki/out.txt","a",encoding="utf-8") as f:
		try:
			f.write(wikiPage+"\t"+photoFile+"\t"+str(icpsr)+"\n")
		except:
			print traceback.format_exc()

def checkPerson(personName, res, tabs):
	try:
		personPartyName = partyName(res["party_code"])
	except:
		personPartyName = "INVALID PARTY NAME NO GOOD."

	print ("\t"*tabs)+str(res["icpsr"])+": Looking up "+personName
	result = json.loads(requests.get(baseURL+personName,headers=headers).text)
	validKeys = []
	for k in result["query"]["pages"]:
		try:
			vk = int(k)
			validKeys.append(vk)
		except:
			pass

	if len(validKeys)==1:
		if validKeys[0]==-1:
			if " Mc" in personName:
				newNamePre, newNamePost = str(personName).rsplit(" Mc",1)
				newNamePost = newNamePost[0].upper() + newNamePost[1:]
				newName = newNamePre+" Mc"+newNamePost
				if newName!=personName:
					print ("\t"*tabs)+"\tNo result found but I think we have a McProblem."
					checkPerson(newName, res, tabs+1)
					return 0
				else:
					return 0				
			else:
				if len(personName.split(" "))>2: # Useless middle name gumming things up?
					newName = personName.split(" ")[0]+" "+personName.rsplit(" ",1)[1]
					result = checkPerson(newName, res, tabs+1)
					if result==-1:
						nameNoInitial = " ".join([x for x in personName.split(" ") if "." not in x])
						if nameNoInitial != personName and nameNoInitial!=newName:
							result = checkPerson(nameNoInitial, res, tabs+1)
							if result==-1:
								print ("\t"*tabs)+"\tNo result found after every possible check we could do"
								return -1
							else:
								return 0
						else:
							return -1
					else:
						return 0
				else:	
					print ("\t"*tabs)+"\tNo result found at all, fall back"
					return -1
		else:
			final = result["query"]["pages"][str(validKeys[0])]["revisions"][0]["*"]
			if "disambiguation" in personName.lower() or "may refer to" in final.lower():
				print ("\t"*tabs)+"\twe're on a disambiguation page"
				possibleChoices = [x.split("\n")[0].strip() for x in result["query"]["pages"][str(validKeys[0])]["revisions"][0]["*"].split("\n*")[1:]]
				maxScore = 0
				rightChoice = ""
				for choice in possibleChoices:
					score = 0
					if "politician" in choice.lower() or "representative" in choice.lower() or "senator" in choice.lower() or "house of" in choice.lower():
						score=score+1
					if "america" in choice.lower():
						score=score+1
					if stateName(res["state_abbrev"]).lower() in choice.lower():
						score=score+1
					if personPartyName.lower() in choice.lower():
						score=score+1
					if "born" in res and str(res["born"]) in choice:
						score=score+1
					if "died" in res and str(res["died"]) in choice:
						score=score+1
					print ("\t"*tabs)+"\t",choice, score
					if score>maxScore:
						maxScore = score
						rightChoice = choice
				print ("\t"*tabs)+"\tWe pick: ",rightChoice
				newChoiceName = rightChoice.split("[[")[1].split("]]")[0]
				checkPerson(newChoiceName, res, tabs+1)
			else:
				if final.lower().startswith("#redirect"):
					newName = final.split("[[")[1].split("]]")[0]
					print ("\t"*tabs)+"\tRedirect to "+newName
					checkPerson(newName, res, tabs+1)
				else:
					score=0
					if stateName(res["state_abbrev"]).lower() in final.lower():
						score=score+1
					if personPartyName.lower() in final.lower():
						score=score+1
					if "politician" in final.lower() or "congressman" in final.lower() or "senator" in final.lower() or "representative" in final.lower():
						score=score+1
					if "born" in res and str(res["born"]) in final:
						score=score+1
					if "died" in res and str(res["died"]) in final:
						score=score+1
					if score>=3:
						print ("\t"*tabs)+"\tProbably the right page, now looking for photo..."
						if "{{Infobox" in final:
							infoBoxText = final.split("{{Infobox")[1].split("}}")[0]
							lines = infoBoxText.split("\n")
							print ("\t"*tabs)+"\tFound an infobox"
							iF=0
							for line in lines:
								line = " ".join(line.split())
								#if "{{Infobox" in final:
								#	print line
								if "=" in line:
									iF=1
									try:
										boiler, filename = line.split("=",1)
									except:
										print line
										print "no idea what happened here but this caused a split error"
									if "image" in boiler and not "image_size" in boiler and not "imagesize" in boiler and not "smallimage" in boiler:
										filename = filename.strip()
										if len(filename) and not "<!--" in filename.lower():
											print ("\t"*tabs)+"\tWe have an image... "+filename
											photoURL = mapPhoto(filename)
											writeGuess(res["bioname"], personName, photoURL, res["icpsr"])
											return 0
										else:
											print ("\t"*tabs)+"\tNo image in bio box."
							if iF==0:
								print ("\t"*tabs)+"\tCouldn't even find space for an image in bio box."
						else:
							try:
								fn = final.split("[[File:",1)[1].split("|",1)[0]
								print ("\t"*tabs)+"\tmaybe this is one... "+fn
								photoURL = mapPhoto(fn)
								writeGuess(res["bioname"], personName, photoURL, res["icpsr"])
							except:
								print ("\t"*tabs)+"\tfailure trying to find non-infobox photo"
					else:
						if "isJunior" in res:
							if "[["+personName.lower()+", jr.]]" in final.lower() and ", jr." not in personName.lower():
								 checkPerson(personName+", Jr.", res, tabs+1)
						else:
							print "In a weird situation."
							#print score
							#print res
							print ("\t"*tabs)+"\tnot looking good... ", personName, stateName(res["state_abbrev"]), partyName(res["party_code"])
							lineSplit = final.split("\n")
							for l in lineSplit:
								if "{{about|" in l.lower():
									print l
									lineChunks = l.split("|")
									print lineChunks
									print ("\t"*tabs)+"\tI think we've found an alternate name person."
									result = checkPerson(lineChunks[3].replace("}}",""),res,tabs+1)
									return result
								elif "{{other people" in l.lower():
									print ("\t"*tabs)+"\tInvestigating a disambiguation"
									lineChunks = l.split("|")
									result = checkPerson(lineChunks[1].replace("}}","") + " (disambiguation)", res, tabs+1)
									return result								
								else:
									pass
							return -1
	else:
		print ("\t"*tabs)+"\tuh oh"
		print validKeys


def do_download(url, icpsr):
	""" Download a specific image. """
	pass

def get_blacklist():
	""" Reads Wikipedia search blacklist and rejects them. """
	return [str(x).zfill(6) for x in open("blacklist.txt", "r").read().split("\n") if len(x)]
	

def get_current_images():
	""" Return the currently available images. """

	bio_guide = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/bio_guide/*.*")])
	wiki = set([x.rsplit("/", 1)[1].split(".")[0] for x in glob.glob("images/wiki/*.*")])

	return bio_guide | wiki

def search_member(member):
	if "bioname" in member:
		fixed_name = " ".join((member["bioname"].split(", ")[1] + " " + member["bioname"].split(", ")[0]).title().split())
		if member["bioname"].lower().endswith(", jr."):
			is_junior = 1
	else:
		print "Error: No full name."
		return

	# headers = {"User-Agent": "VoteViewBioImageScraper/1.1 (rudkin@ucla.edu; Part of NOMINATE/VoteView Congressional Ideology Project)" }
	# baseURL = "http://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&format=json&titles="
	# wikiBanned = [int(x.strip()) for x in open("banWiki.txt","r").read().split("\n") if len(x)]
	# checkPerson(fixedName, res, 0)
	# i=i+1
	
def db_scrape(congress, resume):
	""" Get members from the database that are missing and scrape them. """

	have_images = get_current_images()
	blacklist = get_blacklist()
	need_images = []
	seen_icpsr = []

	connection = pymongo.MongoClient()  
	db = connection["voteview"]
	db.voteview_members.ensure_index([("icpsr", pymongo.ASCENDING)])

	query = {"congress": {"$gte": congress}}
	keep_fields = {x: 1 for x in ["bioname", "congress", "icpsr", "party_code", "state_abbrev", "born", "died"]}
	keep_fields["_id"] = 0

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
		if padded_icpsr in blacklist:
			continue

		need_images.append(result)

	# Now actually do the remote searches
	for member in need_images:
		try:
			print("Searching for member %s %s..." % (str(member["icpsr"]).zfill(6), member["bioname"]))
			search_member(member)
		except:
			print("\t Failed while searching for member.")
			print traceback.format_exc()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description = "Scrape Wikipedia for congressional photos.")
	parser.add_argument("min", type=int, default=90, nargs="?")
	parser.add_argument("resume", type=int, default=0, nargs="?")
	arguments = parser.parse_args()

	db_scrape(arguments.min, arguments.resume)

