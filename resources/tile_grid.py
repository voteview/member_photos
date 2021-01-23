""" Generates gridded walls of images from individual congress/chambers. """

import csv
import random
from PIL import Image

def load_scale(filename):
    """ Loads a single image and scales it to 120xheight """

    image = Image.open(filename)
    original_size = image.size
    new_width = 120
    new_height = original_size[1] * (120 / float(original_size[0]))
    image.thumbnail((new_width, new_height), Image.ANTIALIAS)
    return image

def build_grid(filenames):
    """ Builds the actual grid images. """

    random.shuffle(filenames)
    image = Image.new("RGB", (1100, 300))
    x = 0 - random.randint(0, 60)
    y = 0 - random.randint(0, 75)
    for filename in filenames:
        print(filename, x, y)
        sprite = load_scale(filename)
        image.paste(sprite, (x, y))
        y = y + sprite.size[1] + 1
        if y > 300:
            x = x + 121
            y = 0 - random.randint(0, 75)
        if x > 1100:
            break

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

def process(congress, chamber, filename_out):
    """ Wraps the entire process. """
    filenames = list_files(congress, chamber)
    print("Detected %s matching member portraits" % len(filenames))
    if filenames:
        grid = build_grid(filenames)
        grid.save(filename_out, "JPEG")

if __name__ == "__main__":
    process(117, "Senate", "senate_grid.jpg")
    process(117, "House", "house_grid.jpg")
