from concurrent.futures import ThreadPoolExecutor, as_completed

from config import FEATURES
from loader import FeatureLoader
from logger import logger

MAX_WORKERS = 5


loader = FeatureLoader()

success = []
failed = []


def run_feature(feature):

    loader.load_feature(feature)

    return feature["name"]


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

    futures = {
        executor.submit(run_feature, feature): feature
        for feature in FEATURES
    }

    for future in as_completed(futures):

        feature = futures[future]

        try:

            future.result()

            logger.info("SUCCESS : %s", feature["name"])

            success.append(feature["name"])

        except Exception as e:

            logger.exception(
                "FAILED : %s",
                feature["name"],
            )

            failed.append(feature["name"])


print("=" * 60)

print(f"Successful : {len(success)}")

print(f"Failed     : {len(failed)}")

print("=" * 60)

if failed:

    print("\nFailed Features\n")

    for feature in failed:

        print(feature)