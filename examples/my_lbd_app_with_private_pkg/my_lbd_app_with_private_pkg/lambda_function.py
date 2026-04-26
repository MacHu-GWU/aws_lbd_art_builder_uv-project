import importlib.metadata
from pathlib import Path


def lambda_handler(event, context):
    package_name = Path(__file__).parent.name
    version = importlib.metadata.version(package_name)
    return {"version": version}
