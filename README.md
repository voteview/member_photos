# member_photos repository

This repository contains code to scrape photos of congresspeople from the congressional bioguide and Wikipedia., as well as the photos we have located (some have been manually located from external sources) and a roster to map the resulting photo files to member identities. Currently, the database layer requires running our MongoDB, and so this is not ready for public consumption.

## Notes

Some commands here:

* `python bio_guide.py --congress 1`: Scrapes the congressional bio guide starting from 1st congress (default starting congress is 105)
* `python wiki.py --min 1`: Scrapes Wikipedia starting from 1st congress (default starting congress is 20)
* `python check_missing.py --min 1 [--chamber House --state CT]`: Checks to see what we're missing starting from 1st congress (default start is 80)
* `python wiki.py --blacklist ICPSR`: If you notice an ICPSR that is connected to an article that misfires, blacklist it.
* `python wiki.py --icpsr ICPSR --url "http://en.wikipedia.org/..."`: Specifically scrapes the provided URL to get the ICPSR (normal scoring rules apply)
* `manual_wiki_override.sh`: Scrapes pre-coded ICPSRs that don't resolve properly
* `constrain_images.sh`: Resizes, format switches, and optimizes images from `images/raw/` into `images/`
* `scrape_all.sh`: Scrapes everything, runs the manual override, and constrains the images.
* `deploy.sh`: Waterfall merges all images and deploys to a target directory

## Config

Config file is `config/config.json`: includes user-agent and some URLs.

`config/wiki_results.json`: Contains blacklist and greylist.

