"""
Crops and resizes images dynamically. Originally implemented as a shell
script, but simpler to track relevant variables and keep track of which
files need processing here.
"""

import argparse
import json
import logging
import subprocess
from pathlib import Path

from wand.image import Image

try:
    from azure.ai.vision.face import FaceClient
    from azure.ai.vision.face.models import (
        FaceAttributeTypeDetection03,
        FaceDetectionModel,
        FaceRecognitionModel,
    )
    from azure.core.credentials import AzureKeyCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
TARGET_WIDTH = 480
TARGET_HEIGHT = 600
MOGRIFY_QUALITY = 75
SMARTCROP_QUALITY = 80
ASPECT_RATIO_MIN = 0.75
ASPECT_RATIO_MAX = 0.85

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def get_output_path(raw_path):
    """Convert a raw image path to its output path."""
    path = Path(raw_path)
    # Replace 'raw/' in the path and change extension to .jpg
    new_path = Path(str(path).replace("raw/", "")).with_suffix(".jpg")
    return new_path


def constrain_folder(folder, override, face_client):
    """Dispatches files in a folder to be constrained."""
    folder_path = Path(folder)
    files = list(folder_path.glob("*.*"))

    if override:
        files_edit = files
    else:
        files_edit = [
            f for f in files
            if not get_output_path(f).exists() or
            get_output_path(f).stat().st_mtime < f.stat().st_mtime
        ]

    if not files_edit:
        logger.info("No files in folder `%s` require constraint.", folder)

    for file_path in files_edit:
        constrain_image(file_path, face_client)


def constrain_image(file_path, face_client):
    """Constrains an individual file."""
    file_path = Path(file_path)
    logger.info("Processing file %s", file_path)

    with Image(filename=str(file_path)) as img_in:
        width, height = img_in.size
        aspect_ratio = width / height
        new_folder = get_output_path(file_path).parent
        new_filename = get_output_path(file_path)

        # Ensure output directory exists
        new_folder.mkdir(parents=True, exist_ok=True)

        if ASPECT_RATIO_MIN < aspect_ratio < ASPECT_RATIO_MAX or "bio_guide" in str(file_path):
            logger.info("\tAspect ratio OK, resizing.")
            args = [
                "mogrify",
                "-verbose",
                "-format", "jpg",
                "-quality", str(MOGRIFY_QUALITY),
                "-resize", f"{TARGET_HEIGHT}x{TARGET_HEIGHT}>",
                "-path", str(new_folder),
                str(file_path)
            ]
        else:
            new_height = height if aspect_ratio > 1 else int(width * 5 / 4)
            new_width = width if aspect_ratio < 1 else int(height * 4 / 5)
            if new_height > TARGET_HEIGHT:
                new_height = TARGET_HEIGHT
                new_width = TARGET_WIDTH
            logger.info(
                "\tRescaling image from %s x %s (AR %.2f) to %s x %s",
                width, height, aspect_ratio, new_width, new_height
            )
            args = [
                "smartcrop",
                "--module", "smartcrop-sharp",
                "--width", str(int(new_width)),
                "--height", str(int(new_height)),
                "--outputFormat", "jpg",
                "--quality", str(SMARTCROP_QUALITY),
                str(file_path),
                str(new_filename)
            ]

        subprocess.run(args, check=True)

        needs_horizontal_flip(new_folder, new_filename, face_client)
        optimize_image(new_filename)


def needs_horizontal_flip(new_folder, new_filename, face_client):
    """
    Check if an image requires a horizontal flip and if so,
    flip it.
    """
    if not face_client:
        return

    needs_flip = False
    new_filename = Path(new_filename)

    try:
        with open(new_filename, "rb") as face_image:
            image_content = face_image.read()
            detected_faces = face_client.detect(
                image_content,
                detection_model=FaceDetectionModel.DETECTION03,
                recognition_model=FaceRecognitionModel.RECOGNITION04,
                return_face_id=False,
                return_face_attributes=[FaceAttributeTypeDetection03.HEAD_POSE]
            )

            if not detected_faces:
                return

            # Yaw is direction facing, positive means facing stage left
            # (our right), negative means facing stage right
            # (our left). We flip to face stage left.
            head_pose = detected_faces[0].face_attributes.head_pose
            needs_flip = head_pose.yaw < 0
    except Exception as e:
        logger.warning("Face API error: %s", e)
        return

    if needs_flip:
        logger.info("\tNeeds flip according to facial recognition AI.")
        subprocess.run(
            ["mogrify", "-flop", "-path", str(new_folder), str(new_filename)],
            check=True
        )


def optimize_image(filename):
    """JPEGOptim and jpegtran optimization."""
    filename = Path(filename)

    subprocess.run(
        ["jpegoptim", "--strip-all", "-P", str(filename)],
        check=True
    )

    subprocess.run(
        ["jpegtran", "-copy", "none", "-optimize",
         "-outfile", str(filename), str(filename)],
        check=True
    )


def preprocess_gifs():
    """Mogrify the Wikipedia GIFs because smartcrop can't handle them."""
    wiki_raw = Path("images/raw/wiki")

    gif_files = list(wiki_raw.glob("*.gif"))
    if not gif_files:
        return

    # Convert GIFs to JPG
    subprocess.run(
        ["mogrify", "-verbose", "-format", "jpg",
         "-path", str(wiki_raw)] + [str(f) for f in gif_files],
        capture_output=True
    )

    # Remove the original GIF files
    for gif_file in gif_files:
        gif_file.unlink(missing_ok=True)


def authorize_facial_detection():
    """Load config and setup Azure Face API."""
    if not AZURE_AVAILABLE:
        return None

    config_path = Path("config/facial_recognition.json")
    if not config_path.exists():
        return None

    with open(config_path) as f:
        all_config = json.load(f)

    face_client = FaceClient(
        endpoint=all_config["endpoint"],
        credential=AzureKeyCredential(all_config["key"])
    )
    return face_client


def main():
    """Parse command line arguments and process images."""
    parser = argparse.ArgumentParser(
        description="Modify aspect ratio of raw images to conform with VV"
    )
    parser.add_argument("--force", action="store_true",
                        help="Force reprocessing of all images")
    arguments = parser.parse_args()

    override = arguments.force
    face_client = authorize_facial_detection()

    constrain_folder("images/raw/wiki/", override, face_client)
    constrain_folder("images/raw/manual/", override, face_client)
    constrain_folder("images/raw/bio_guide/", override, face_client)


if __name__ == "__main__":
    preprocess_gifs()
    main()
