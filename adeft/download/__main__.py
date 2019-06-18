import os
import argparse

from adeft.download import download_models, setup_test_resource_folders, \
    download_test_resources
from adeft.locations import ADEFT_PATH, ADEFT_MODELS_PATH, \
    TEST_RESOURCES_PATH


"""
Allows models to be downloaded from the command line with
python -m adeft.download

Use python -m adeft.download --update
to update existing models if models have changed on S3
"""

parser = argparse.ArgumentParser(description='Download models from S3')
parser.add_argument('--update', action='store_true',
                    help='Update existing models if they have changed on S3')
args = parser.parse_args()

# Create .adeft folder if it does not already exist
if not os.path.exists(ADEFT_PATH):
    os.mkdir(ADEFT_PATH)
    os.mkdir(ADEFT_MODELS_PATH)


setup_test_resource_folders()
download_test_resources()
download_models(update=args.update)
