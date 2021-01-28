""" Very quick hack to delete bio guide result and replace with found wiki result. """
import json
import sys
import os
import subprocess

icpsr = sys.argv[1].zfill(6)
wiki_url = sys.argv[2]

try:
    os.remove("images/bio_guide/%s.jpg" % icpsr)
    os.remove("images/raw/bio_guide/%s.jpg" % icpsr)
except:
    pass

subprocess.call(
    '/usr/bin/python2.7 wiki.py --icpsr %s --url "%s"' % (icpsr, wiki_url),
    shell=True
)

with open("config/bio_guide_results.json", "r") as f:
	data = json.load(f)

data["blacklist"] = list(set(data["blacklist"] + [icpsr]))
data["blacklist"].sort()
with open("config/bio_guide_results.json", "w") as f:
	json.dump(data, f)

