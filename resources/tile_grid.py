""" Generates gridded walls of images from individual congress/chambers. """

import csv
import random
from pymongo import MongoClient
from PIL import Image

def load_scale(filename, width_scale=120):
    """ Loads a single image and scales it to 120xheight """

    image = Image.open(filename)
    original_size = image.size
    new_width = width_scale
    new_height = int(original_size[1] * (width_scale / float(original_size[0])))

    image = image.resize((new_width, new_height), Image.LANCZOS)
    return image

def build_grid(filenames, width_scale=120, seed=1234):
    """ Builds the actual grid images. """

    print("Building grid with width %s and seed %s" % (width_scale, seed))
    random.Random(seed).shuffle(filenames)
    image = Image.new("RGB", (1100, 300))
    x = 0 - random.randint(0, width_scale / 2)
    y = 0 - random.randint(0, 75)
    for filename in filenames:
        print(filename, x, y)
        sprite = load_scale(filename, width_scale)
        image.paste(sprite, (x, y))
        y = y + sprite.size[1] + 1
        if y > 300:
            x = x + width_scale + 1
            y = 0 - random.randint(0, 75)
        if x > 1100:
            break

    if x < 1000:
        print("Note: Grid image not filled.")

    return image

def list_files(congress, chamber):
    """ List all images relevant to a given congress and chamber. """

    all_members = []
    with open("../members.csv") as read_file:
        reader = csv.DictReader(read_file)
        for row in reader:
            all_members.append(row)

    return [x["image"].replace("images/", "../images/")
            for x in all_members if x["congress"] == str(congress) and
            x["chamber"] == chamber and x["image"]]

def list_files_icpsr(icpsrs):
    """ List all images in a certain set of ICPSRs. """

    all_members = []
    with open("../members.csv") as read_file:
        reader = csv.DictReader(read_file)
        for row in reader:
            all_members.append(row)

    icpsrs_str = [str(x).zfill(6) for x in icpsrs]

    return [x["image"].replace("images/", "../images/")
            for x in all_members if x["icpsr"] in icpsrs_str and
            x["image"]]


def process_congress(congress, chamber, filename_out, width_scale=120):
    """ Wraps the entire process of generating a chamber/congress. """
    print((
        "Generating tiles based on congress:\nCongress %s, Chamber %s" %
        (congress, chamber)))
    filenames = list_files(congress, chamber)
    print("Detected %s matching member portraits" % len(filenames))
    if filenames:
        grid = build_grid(filenames, width_scale=width_scale)
        grid.save(filename_out, "JPEG")


def process_query(query, width_scale, filename_out):
    """ Wraps the entire process of generating based on a db query. """
    print("Generating tiles based on query:")
    print(query)
    connection = MongoClient()
    db = connection["voteview"]

    icpsrs = []
    for row in db.voteview_members.find(query, {"icpsr": 1, "_id": 0}):
        icpsrs.append(row["icpsr"])

    icpsrs = list(set(icpsrs))
    filenames = list_files_icpsr(icpsrs)
    print("Detected %s matching member portraits" % len(filenames))
    if filenames:
        grid = build_grid(filenames, width_scale=width_scale)
        grid.save(filename_out, "JPEG")


if __name__ == "__main__":
    process_congress(117, "Senate", "senate_grid.jpg", 120)
    process_congress(117, "House", "house_grid.jpg", 120)
    process_query({"served_as_speaker": 1}, 120, "speaker_grid.jpg")
    process_query({"served_as_maj_leader": 1}, 240, "maj_leader_grid.jpg")
