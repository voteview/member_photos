# member_photos repository

This repository contains photos of U.S. congressional representatives through the ages, as well as code necessary to regenerate this data from scratch. We currently have approximately 9,700 of 12,300 representatives accounted for. 

## How to Use

### Check for Missing

`check_missing.py` allows users to check for representatives whose photos are missing and generates a table based on criteria provided.

Arguments:

* `--type flat`: Use a flatfile database instead of our default MongoDB instance. Most end users should use this argument.
* `--min N`: Provide a number `N` which represents the minimum Congress to scan for missing photos (default `81` [1947-1949])
* `--chamber chamber`: Province a chamber `chamber` describing a specific chamber of congress. Valid options are `House` or `Senate`. Default is left blank.
* `--state state`: Province a two-character `state` postal abbreviation to limit searches to one state. Example: `CO` for Colorado.
* `--sort sort`: Provid a string `sort` which describes which field to sort on. Valid options are `bioname`, `icpsr`, `state_abbrev`, `party_code`, `congress`. Default is `congress`.

Example usage:

`python check_missing.py --type flat --min 50 --state CT --chamber House --sort bioname`

### Scrape Congressional Bioguide

`bio_guide.py` allows users to scrape the [Congressional Bioguide](http://bioguide.congress.gov/biosearch/biosearch.asp) for photos.

Arguments:

* `--type flat`: Use a flatfile database instead of our default MongoDB instance. Most end users should use this argument.
* `--min N`: Provide a number `N` which represents the minimum Congress to scan for missing photos (default `20`)

Example usage:

`python bio_guide.py --type flat --min 50`

### Scrape Wikipedia

`wiki.py` allows users to scrape Wikipedia for photos.

Arguments:

* `--type flat`: Use a flatfile database instead of our default MongoDB instance. Most end users should use this argument.
* `--min N`: Provide a number `N` which represents the minimum Congress to scan for missing photos (default `20`)
* `--icpsr ICPSR --url "http://..."`: Provide an ICPSR and a URL to manually scrape a Wikipedia article for that ICPSR. Useful when the default name or search is inadequate. The resulting page will still be checked against the scoring algorithm to ensure the page is appropriate for the member.
* `--blacklist ICPSR`: Mutually exclusive to all other arguments; tells the scraper to not scrape this ICPSR from Wikipedia in the future. Useful when the correct page has a photo that is incorrectly scraped (i.e. house or memorial photo or military insignia instead of photo of person).

Example usage:

`python wiki.py --type flat --min 50`

`manual_wiki_override.sh` will scrape photos for all our currently known cases where the default scraper scrapes an incorrect photo or misses the search query.

### Process Photos

* `constain_images.sh` will resice, format size, and optimize images. Images will move from `images/raw/<source>/<file>.<ext>` to `images/<source>/<file>.jpg`
* `scrape_all.sh` will scrape Bioguide, Wikipedia, and then constrain the images in order.

### Configuration

* `config/config.json`: User-Agent for scraper and some default URLs.
* `config/wiki_results.json`: Blacklist for Wikipedia and greylist (articles recently scraped, confirmed to contain nothing, skip for a while)
* `config/parties.json`: Party metadata, used for both checking Wikipedia articles and outputting party names.
* `config/states.json`: State metadata, used for both checking Wikipedia articles and outputting party names.
* `config/database-raw.json`: Large raw database dump, used for flat-file searches.

### Mongo DB dump

* `config/dump_db.py`: Dumps current database to flatfile. Requires our local MongoDB instance.

## Contributing

We welcome contributions of photos or code improvements. For code improvements, please open a pull request.

For sources for photos, please see our [Issues](https://github.com/voteview/member_photos/issues) page. If you are contributing a photo to an existing project, just reply with a comment including the photo (highest resolution possible, include information about where the photo is from and any rights issues). If no project seems applicable, or if you are letting us know about a new source of many photos, please open a new Issue.

## Next Steps

1. Produce a CSV flatfile output that combines bio info, ICPSRs, and provenance info.
2. Center cropping for face portraits for the output images
3. `deploy.sh` to deploy downscaled images to production environment.
3. More documentation for end users.

