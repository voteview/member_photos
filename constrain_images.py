"""
Crops and resizes images dynamically. Originally implemented as a shell
script, but simpler to track relevant variables and keep track of which
files need processing here.
"""

import glob
import json
import os
import subprocess
import argparse
from wand.image import Image
from azure.cognitiveservices.vision.face import FaceClient
from msrest.authentication import CognitiveServicesCredentials
from requests.packages import urllib3
urllib3.disable_warnings()


def constrain_folder(folder, override, face_client):
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

    if not files_edit:
        print("No files in folder `%s` require constraint." % folder)

    for file_name in files_edit:
        constrain_image(file_name, face_client)

def constrain_image(file_name, face_client):
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

        # print(args)
        call = " ".join(args)
        subprocess.call(call, shell=True)

        needs_horizontal_flip(new_folder, new_filename, face_client)
        optimize_image(new_filename)


def needs_horizontal_flip(new_folder, new_filename, face_client):
    """
    Check if an image requires a horizontal flip and if so,
    flip it.
    """

    needs_flip = False

    if face_client:
        attribs = ["age", "gender", "headPose", "facialHair"]
        with open(new_filename, "rb") as face_image:
            detected_face = face_client.face.detect_with_stream(
                face_image,
                return_face_attributes=attribs)

            if not detected_face:
                return

            result = detected_face[0].face_attributes.as_dict()
            # Yaw is direction facing, positive means facing stage left
            # (our right), negative means facing stage right
            # (our left). We flip to face stage left.
            needs_flip = True if result["head_pose"]["yaw"] < 0 else False

    if needs_flip:
        print("\t Needs flip according to facial recognition AI.")
        subprocess.call(
            "mogrify -flop -path %s %s" % (new_folder, new_filename),
            shell=True
        )


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

def preprocess_gifs():
    """ Mogrify the Wikipedia GIFs because smartcrop can't handle them. """

    # Write to /dev/null, since most of the time these calls just produce
    # an error with no GIF files in the folder
    with open(os.devnull, "wb") as sink_out:
        subprocess.call(
            "mogrify -verbose -format jpg -path images/raw/wiki images/raw/wiki/*.gif",
            stderr=sink_out,
            stdout=sink_out,
            shell=True
        )

        subprocess.call(
            "rm images/raw/wiki/*.gif",
            stderr=sink_out,
            stdout=sink_out,
            shell=True
        )


def authorize_facial_detection():
    if not os.path.isfile("config/facial_recognition.json"):
        return None

    all_config = json.load(open("config/facial_recognition.json", "r"))
    face_client = FaceClient(all_config["endpoint"], CognitiveServicesCredentials(all_config["key"]))
    return face_client


def parse_arguments():
    """ Parse command line arguments and do a full override if necessary. """
    parser = argparse.ArgumentParser(
        description="Modify aspect ratio of raw images to confirm with VV"
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    override = 1 if arguments.force else 0
    face_client = authorize_facial_detection()
    constrain_folder("images/raw/wiki/", override, face_client)
    constrain_folder("images/raw/manual/", override, face_client)
    constrain_folder("images/raw/bio_guide/", override, face_client)

if __name__ == "__main__":
    preprocess_gifs()
    parse_arguments()
