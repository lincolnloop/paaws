import datetime
import getpass
import json
from getpass import getuser
from typing import List

from ..app import app
from .shell import shell_to_task
from ..utils import halo_success, wait_for_task, run_task_until_disconnect

import boto3
import click
from halo import Halo


def s3_location(app_name: str, prefix: str) -> (str, str):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    object_name = f"{prefix}{timestamp}-{getpass.getuser()}.dump"
    return app.settings["db_utils"]["s3_bucket"], object_name


def run_task(app_name: str, definition: str, command: List[str]) -> str:
    # Fetch the default runTask arguments from parameter store
    try:
        ssm = boto3.client("ssm")
        run_task_kwargs = json.loads(
            ssm.get_parameter(Name=f"/paaws/apps/{app_name}/ecs-config")["Parameter"][
                "Value"
            ]
        )["run_task_args"]
    except ssm.exceptions.ParameterNotFound:
        run_task_kwargs = {"cluster": app.cluster}

    run_task_kwargs["overrides"] = {
        "containerOverrides": [{"name": "app", "command": command}]
    }
    ecs = boto3.client("ecs")
    task_arn = ecs.run_task(
        taskDefinition=definition,
        startedBy=f"paaws-cli/db-shell/{getuser()}",
        **run_task_kwargs,
    )["tasks"][0]["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    return task_arn


def download_file(bucket: str, object_name: str, local_file: str) -> None:
    with halo_success(text=f"downloading file {local_file}", spinner="dots"):
        s3 = boto3.client("s3")
        s3.download_file(bucket, object_name, local_file)


def upload_file(local_file: str, bucket: str, object_name: str) -> None:
    with halo_success(text=f"uploading file {local_file}", spinner="dots"):
        s3 = boto3.client("s3")
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
    bucket, object_name = s3_location(app.name, "dumps/")
    print(json.dumps(app.settings, indent=2))
    print(app.settings["db_utils"]["dumpload_task_family"])
    task_arn = run_task(
        app.name,
        app.settings["db_utils"]["dumpload_task_family"],
        ["dump-to-s3.sh", f"s3://{bucket}/{object_name}"],
    )
    wait_for_task(app.cluster, task_arn, "dumping database")
    download_file(bucket, object_name, f"{app.name}.dump")


@db.command()
@click.argument("local_file")
def load(local_file: str):
    """Replace remote database with local dump"""
    bucket, object_name = s3_location(app.name, "uploads/")
    upload_file(local_file, bucket, object_name)
    task_arn = run_task(
        app.name,
        app.settings["db_utils"]["dumpload_task_family"],
        ["load-from-s3.sh", f"s3://{bucket}/{object_name}"],
    )
    wait_for_task(app.name, task_arn, "loading database")


@db.command()
def shell():
    """
    Run an interactive database shell
    """
    ecs = boto3.client("ecs")
    task = run_task_until_disconnect(
        cluster=app.cluster, task_defn=app.settings["db_utils"]["shell_task_family"]
    )
    task_arn = task["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    wait_for_task(app.cluster, task_arn, "running container", status="tasks_running")
    shell_to_task(task, app.cluster, command="entrypoint.sh psql")
