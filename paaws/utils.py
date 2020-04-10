from getpass import getuser
from contextlib import contextmanager
from typing import List, Optional

import boto3
from halo import Halo


@contextmanager
def halo_success(*args, **kwargs):
    spinner = Halo(*args, **kwargs)
    try:
        yield spinner.start()
    finally:
        spinner.succeed()


def tags_match(tags: List[dict], expected_tags: List[dict]) -> bool:
    """Is expected_tags a subset of tags?"""
    return all([tag in tags for tag in expected_tags])


def wait_for_task(
    cluster: str, arn: str, message: str = "running task", status: str = "tasks_stopped"
) -> None:
    spinner = Halo(text=message, spinner="dots").start()
    ecs = boto3.client("ecs")
    ecs.get_waiter(status).wait(cluster=cluster, tasks=[arn])
    if status == "tasks_stopped":
        container = ecs.describe_tasks(cluster=cluster, tasks=[arn])["tasks"][0][
            "containers"
        ][0]
        if int(container.get("exitCode", "255")) > 0:
            spinner.fail()
            exit(1)
    spinner.succeed()


def run_task_until_disconnect(
    cluster: str, task_defn: str, container: Optional[str] = None
) -> dict:
    command = [
        "/bin/sh",
        "-c",
        'STOP=$(($(date +%s)+43200)); sleep 60; while true; do  PROCS="$(ls /proc | grep [0-9] | wc -l)"; test "$PROCS" -lt "6" && exit; test "$STOP" -lt "$(date +%s)" && exit 1; sleep 30; done',
    ]
    ecs = boto3.client("ecs")
    if not container:
        container = ecs.describe_task_definition(taskDefinition=task_defn)[
            "taskDefinition"
        ]["containerDefinitions"][0]["name"]

    return ecs.run_task(
        taskDefinition=task_defn,
        cluster=cluster,
        startedBy=f"paaws-cli/shell/{getuser()}",
        overrides={"containerOverrides": [{"name": container, "command": command}]},
    )["tasks"][0]
