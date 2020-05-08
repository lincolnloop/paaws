import logging
from textwrap import indent

import boto3
import click
from halo import Halo
from termcolor import cprint, colored

from ..app import app
from ..utils import formatted_time_ago

log = logging.getLogger(__name__)


def get_artifact(build: dict, name: str) -> str:
    if not build["artifacts"]["location"]:
        log.debug("No artifacts stored by Codebuild. Skipping download of %s", name)
        return ""
    artifact_arn = build["artifacts"]["location"]
    parts = ":".join(artifact_arn.split(":")[5:])
    bucket, key_prefix = parts.split("/", 1)
    s3 = boto3.client("s3")
    body = s3.get_object(Bucket=bucket, Key=f"{key_prefix}/{name}")["Body"]
    return body.read().decode("utf-8")


STATUS_MAP = {
    "IN_PROGRESS": "info",
    "SUCCEEDED": "succeed",
    "FAILED": "fail",
}


def print_build(build: dict) -> None:
    first_line = [
        colored("===", attrs=["dark"]),
        colored(str(build["buildNumber"]), "white"),
    ]
    if build["buildStatus"] == "IN_PROGRESS":
        first_line.append("in progress")
    first_line.append(colored(build["sourceVersion"], "blue"))
    getattr(
        Halo(text=" ".join(first_line), placement="right"),
        STATUS_MAP[build["buildStatus"]],
    )()
    if "endTime" in build:
        print(indent(formatted_time_ago(build["endTime"]), 4 * " "))
    else:
        print(indent("started " + formatted_time_ago(build["startTime"]), 4 * " "))
    s3 = boto3.client("s3")
    try:
        cprint(indent(get_artifact(build, "commit.txt"), 4 * " "))
    except s3.exceptions.NoSuchKey:
        print("")


def find_build_by_number(build_number: int, limit: int = 20) -> dict:
    builds = app.get_builds(limit=limit)
    try:
        return [b for b in builds if b["buildNumber"] == int(build_number)][0]
    except IndexError:
        raise Exception("Not found")


@click.group()
def builds():
    """View build information"""
    pass


@builds.command()
def list():
    """List most recent builds"""
    for b in app.get_builds(limit=5):
        print_build(b)


@builds.command()
@click.argument("id")
def view(id):
    """View status for a specific build"""
    build = find_build_by_number(id)
    print_build(build)


@builds.command()
@click.argument("id")
@click.argument(
    "log_type", type=click.Choice(["build", "test", "release"]), default="test"
)
def logs(id, log_type):
    """View build or test logs for a specific build"""
    with Halo(f"downloading {log_type} log", spinner="dots"):
        print("\n" + get_artifact(find_build_by_number(id), f"{log_type}.log"))
