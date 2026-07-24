from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_fixed

from config import CONFIG

retry_feature = retry(
    stop=stop_after_attempt(CONFIG["retry"]["attempts"]),
    wait=wait_fixed(CONFIG["retry"]["wait_seconds"]),
    reraise=True
)