import datetime
import getpass
from getpass import getuser
from typing import List

from ..app import app
from .shell import shell_to_task
from ..utils import halo_success, wait_for_task, run_task_until_disconnect

import click
from halo import Halo


def s3_location(prefix: str) -> (str, str):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    object_name = f"{prefix}{timestamp}-{getpass.getuser()}.dump"
    return app.settings["dbutils"]["s3_bucket"], object_name


def run_task(app_name: str, definition: str, command: List[str]) -> str:
    # Fetch the default runTask arguments from parameter store
    try:
        run_task_kwargs = app.dynamodb_item("CONFIG#ecs")["run_task_args_fargate"]
    except KeyError:
        run_task_kwargs = {"cluster": app.cluster}

    run_task_kwargs["overrides"] = {
        "containerOverrides": [{"name": "app", "command": command}]
    }
    ecs = app.boto3_client("ecs")
    task_arn = ecs.run_task(
        taskDefinition=definition,
        startedBy=f"paaws-cli/db-shell/{getuser()}",
        **run_task_kwargs,
    )["tasks"][0]["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    return task_arn


def download_file(bucket: str, object_name: str, local_file: str) -> None:
    with halo_success(text=f"downloading file {local_file}", spinner="dots"):
        s3 = app.boto3_client("s3")
        s3.download_file(bucket, object_name, local_file)


def upload_file(local_file: str, bucket: str, object_name: str) -> None:
    with halo_success(text=f"uploading file {local_file}", spinner="dots"):
        s3 = app.boto3_client("s3")
        s3.upload_file(local_file, bucket, object_name)


@click.group()
def db():
    """Perform database tasks"""
    pass


@db.command()
def dump():
    """
    Dump database to local file
    """
    bucket, object_name = s3_location("dumps/")
    task_arn = run_task(
        app.name,
        app.settings["dbutils"]["dumpload_task_family"],
        ["dump-to-s3.sh", f"s3://{bucket}/{object_name}"],
    )
    wait_for_task(app.boto3_client("ecs"), app.cluster, task_arn, "dumping database")
    download_file(bucket, object_name, f"{app.name}.dump")


@db.command()
@click.argument("local_file")
def load(local_file: str):
    """Replace remote database with dump from local filesystem or S3 (s3://...)"""
    if local_file.startswith("s3://"):
        remote_file = local_file
    else:
        bucket, object_name = s3_location("uploads/")
        upload_file(local_file, bucket, object_name)
        remote_file = f"s3://{bucket}/{object_name}"
    task_arn = run_task(
        app.name,
        app.settings["dbutils"]["dumpload_task_family"],
        ["load-from-s3.sh", remote_file],
    )
    wait_for_task(app.boto3_client("ecs"), app.cluster, task_arn, "loading database")


@db.command()
def shell():
    """
    Run an interactive database shell
    """
    ecs = app.boto3_client("ecs")
    task = run_task_until_disconnect(
        ecs,
        app.dynamodb_item("CONFIG#ecs"),
        task_defn=app.settings["dbutils"]["shell_task_family"],
    )
    if task is None:
        exit(1)
    task_arn = task["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    wait_for_task(
        ecs, app.cluster, task_arn, "running container", status="tasks_running"
    )
    shell_to_task(task, app.cluster, command="entrypoint.sh psql")