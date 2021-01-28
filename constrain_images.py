"""
Crops and resizes images dynamically. Originally implemented as a shell
script, but simpler to track relevant variables and keep track of which
files need processing here.
"""

import glob
import os
import subprocess
import argparse
from wand.image import Image

def constrain_folder(folder, override):
    """ Dispatches files in a folder to be constrained. """
    files = glob.glob("%s*.*" % folder)
    if override:
        files_edit = files
    else:
        files_resized = ["%s.jpg" % x.replace("raw/", "").rsplit(".", 1)[0]
                         for x in files]
        files_edit = [x for x, y in zip(files, files_resized)
                      if not os.path.isfile(y) or
                      os.path.getmtime(y) < os.path.getmtime(x)]

    for file_name in files_edit:
        constrain_image(file_name)

def constrain_image(file_name):
    """ Constrains an individual file. """
    print("Processing file %s" % file_name)
    with Image(filename=file_name) as img_in:
        aspect_ratio = float(img_in.size[0]) / float(img_in.size[1])
        width = img_in.size[0]
        height = img_in.size[1]
        new_folder = file_name.replace("raw/", "").rsplit("/", 1)[0]
        new_filename = ("%s.jpg" %
                        file_name.replace("raw/", "").rsplit(".", 1)[0])

        if (0.75 < aspect_ratio < 0.85 or "bio_guide" in file_name):
            print("\t Aspect ratio OK, resizing.")
            args = ["mogrify", "-verbose", "-format jpg", "-quality 75",
                    '-resize "600x600>"', "-path %s" % new_folder, file_name]
        else:
            new_height = height if aspect_ratio > 1 else (width * 5/4)
            new_width = width if aspect_ratio < 1 else (height * 4/5)
            if new_height > 600:
                new_height = 600
                new_width = 480
            print("\t Rescaling image from %s x %s (AR %s) to %s x %s" %
                  (width, height, aspect_ratio, new_width, new_height))
            args = ["smartcrop", "--width %s" % new_width, "--height %s" %
                    new_height, "--faceDetection", "--outputFormat jpg",
                    "--quality 80", file_name, new_filename]

        print(args)
        call = " ".join(args)
        subprocess.call(call, shell=True)

        optimize_image(new_filename)

def optimize_image(filename):
    """ JPEGOptim and Trim as possible. """

    subprocess.call(
        "jpegoptim --strip-all -P %s" % filename,
        shell=True
    )

    subprocess.call(
        "jpegtran -copy none -optimize -outfile %s %s" % (filename, filename),
        shell=True
    )

def parse_arguments():
    """ Parse command line arguments and do a full override if necessary. """
    parser = argparse.ArgumentParser(
        description="Modify aspect ratio of raw images to confirm with VV"
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    override = 1 if arguments.force else 0
    constrain_folder("images/raw/wiki/", override)
    constrain_folder("images/raw/manual/", override)
    constrain_folder("images/raw/bio_guide/", override)

if __name__ == "__main__":
    parse_arguments()
