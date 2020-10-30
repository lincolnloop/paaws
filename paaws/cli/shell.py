import os
import sys
from shutil import which
from typing import NoReturn

import click
from halo import Halo
from termcolor import cprint, colored

from .auth import get_credentials
from ..app import app
from ..utils import run_task_until_disconnect, wait_for_task


def shell_to_task(task: dict, cluster: str, command: str = "bash -l") -> NoReturn:
    ecs = app.boto3_client("ecs")
    instance_id = ecs.describe_container_instances(
        cluster=cluster, containerInstances=[task["containerInstanceArn"]]
    )["containerInstances"][0]["ec2InstanceId"]
    arn = task["taskArn"]
    creds = get_credentials(app.name)
    os.execlpe(
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
        {
            "AWS_ACCESS_KEY_ID": creds["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["SecretAccessKey"],
            "AWS_SESSION_TOKEN": creds["SessionToken"],
            **os.environ
        }
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
    ecs = app.boto3_client("ecs")
    task = run_task_until_disconnect(ecs, app._load_config("ecs-config"), app.settings["shell"]["task_family"])
    if task is None:
        exit(1)
    task_arn = task["taskArn"]
    Halo(text=f"starting task {task_arn}").info()
    wait_for_task(ecs, app.cluster, task_arn, "running container", status="tasks_running")
    shell_to_task(task, app.cluster, app.settings["shell"]["command"])
