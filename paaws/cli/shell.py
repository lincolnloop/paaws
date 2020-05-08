import os
import sys
from shutil import which
from typing import NoReturn

import boto3
import click
from halo import Halo
from termcolor import cprint, colored

from ..app import app
from ..utils import run_task_until_disconnect, wait_for_task


def shell_to_task(task: dict, cluster: str, command: str = "bash -l") -> NoReturn:
    ecs = boto3.client("ecs")
    instance_id = ecs.describe_container_instances(
        cluster=cluster, containerInstances=[task["containerInstanceArn"]]
    )["containerInstances"][0]["ec2InstanceId"]
    arn = task["taskArn"]
    os.execlp(
        sys.executable,
        "aws",
        "-m",
        "awscli",
        "ssm",
        "start-session",
        "--target",
        instance_id,
        "--document-name",
        "AWS-StartInteractiveCommand",
        "--parameters",
        # TODO: check if fargate and remove docker
        f"command=sudo docker exec -it $(sudo docker ps -q -f label=com.amazonaws.ecs.task-arn={arn}) {command}",
    )


@click.command()
def shell():
    """Open an interactive shell in the remote environment"""
    if not which("session-manager-plugin"):
        cprint("Session Manager Plugin is not installed", "red")
        print(
            "Installation instructions:",
            colored(
                "https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html",
                "white",
            ),
        )
        exit(1)
    task = run_task_until_disconnect(app.cluster, app.settings["shell"]["task_family"])
    task_arn = task["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    wait_for_task(app.cluster, task_arn, "running container", status="tasks_running")
    shell_to_task(task, app.cluster, app.settings["shell"]["command"])
