from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

with open(ROOT / "config" / "features.yaml") as f:
    FEATURES = yaml.safe_load(f)["features"]