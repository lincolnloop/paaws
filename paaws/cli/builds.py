from pydoc import pager

import boto3
import click
from halo import Halo

from ..app import app


def get_artifact(build: dict, name: str) -> str:
    artifact_arn = build["artifacts"]["location"]
    parts = ":".join(artifact_arn.split(":")[5:])
    bucket, key_prefix = parts.split("/", 1)
    s3 = boto3.client("s3")
    body = s3.get_object(Bucket=bucket, Key=f"{key_prefix}/{name}")["Body"]
    return body.read().decode("utf-8")


@click.group()
def builds():
    pass


@builds.command()
def list():
    codebuild = boto3.client("codebuild")
    # TODO: variable project name
    builds = codebuild.batch_get_builds(
        ids=codebuild.list_builds_for_project(projectName=app.name)["ids"][:5]
    )["builds"]
    status_map = {
        "IN_PROGRESS": "info",
        "SUCCEEDED": "succeed",
        "FAILED": "fail",
    }
    for b in builds:
        getattr(
            Halo(
                text=" ".join(
                    [str(b["buildNumber"]), b["buildStatus"], b["sourceVersion"]]
                )
            ),
            status_map[b["buildStatus"]],
        )()
        if "endTime" in b:
            print(b["endTime"].isoformat())
        else:
            print("")
        try:
            print(get_artifact(b, "commit.txt"))
            print("")
        except Exception:  # TODO: NoSuchKey
            pass


@builds.command()
@click.argument("id")
def view(id):
    codebuild = boto3.client("codebuild")
    builds = codebuild.batch_get_builds(
        ids=codebuild.list_builds_for_project(projectName=app.name)["ids"][:20]
    )["builds"]
    try:
        build = [b for b in builds if b["buildNumber"] == int(id)][0]
    except IndexError:
        raise Exception("Not found")
    pager(get_artifact(build, "test.log"))
