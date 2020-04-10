from pydoc import pager
from textwrap import indent

import boto3
import click
from halo import Halo
from termcolor import cprint, colored

from ..app import app
from ..utils import formatted_time_ago


def get_artifact(build: dict, name: str) -> str:
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
        print("")
    s3 = boto3.client("s3")
    try:
        cprint(indent(get_artifact(build, "commit.txt"), 4 * " "))
    except s3.exceptions.NoSuchKey:
        print("")


def find_build_by_number(build_number: int, limit: int = 20) -> dict:
    codebuild = boto3.client("codebuild")
    builds = codebuild.batch_get_builds(
        ids=codebuild.list_builds_for_project(projectName=app.name)["ids"][:limit]
    )["builds"]
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
    codebuild = boto3.client("codebuild")
    # TODO: variable project name
    builds = codebuild.batch_get_builds(
        ids=codebuild.list_builds_for_project(projectName=app.name)["ids"][:5]
    )["builds"]

    for b in builds:
        print_build(b)


@builds.command()
@click.argument("id")
def view(id):
    """View status for a specific build"""
    build = find_build_by_number(id)
    print_build(build)


@builds.command()
@click.argument("id")
@click.argument("log_type", type=click.Choice(["build", "test"]), default="test")
def logs(id, log_type):
    """View build or test logs for a specific build"""
    pager(get_artifact(find_build_by_number(id), f"{log_type}.log"))
