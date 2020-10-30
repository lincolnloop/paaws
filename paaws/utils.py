import datetime
from getpass import getuser
from contextlib import contextmanager
from typing import List, Optional, NoReturn

import timeago
from halo import Halo
from termcolor import colored


@contextmanager
def halo_success(*args, **kwargs):
    spinner = Halo(*args, **kwargs)
    try:
        yield spinner.start()
    finally:
        spinner.succeed()


def fail(message: str) -> NoReturn:
    Halo(text=message, text_color="red").fail()
    exit(1)


def success(message: str) -> None:
    Halo(text=message, text_color="green").succeed()

def tags_match(tags: List[dict], expected_tags: List[dict]) -> bool:
    """Is expected_tags a subset of tags?"""
    return all([tag in tags for tag in expected_tags])


def wait_for_task(
    ecs, cluster: str, arn: str, message: str = "running task", status: str = "tasks_stopped"
) -> None:
    spinner = Halo(text=message, spinner="dots").start()
    ecs.get_waiter(status).wait(cluster=cluster, tasks=[arn])
    if status == "tasks_stopped":
        container = ecs.describe_tasks(cluster=cluster, tasks=[arn])["tasks"][0][
            "containers"
        ][0]
        if int(container.get("exitCode", "255")) > 0:
            spinner.fail()
            exit(1)
    spinner.succeed()


def run_task_until_disconnect(ecs_client, ecs_config: dict, task_defn: str) -> Optional[dict]:
    """
    Create a task that with a shell command that runs as long as a user is connected
    to the container. A 12 hour timeout is set to kill the container in case an
    orphaned process.
    """
    task_desc = ecs_client.describe_task_definition(taskDefinition=task_defn)["taskDefinition"]
    wait_for_connect = 60
    max_lifetime = 12 * 60 * 60  # 12 hours
    command = [
        "/bin/sh",
        "-c",
        "; ".join(
            [
                # Get initial proc count
                'EXPECTED_PROCS="$(ls -1 /proc | grep -c [0-9])"',
                f"STOP=$(($(date +%s)+{max_lifetime}))",
                # Give user time to connect
                f"sleep {wait_for_connect}",
                # Loop until procs are less than or equal to initial count
                # As long as a user has a shell open, this task will keep running
                "while true",
                'do PROCS="$(ls -1 /proc | grep -c [0-9])"',
                'test "$PROCS" -le "$EXPECTED_PROCS" && exit',
                # Timeout if exceeds max lifetime
                'test "$STOP" -lt "$(date +%s)" && exit 1',
                "sleep 30",
                "done",
            ]
        ),
    ]

    from .cli.auth import get_email
    resp = ecs_client.run_task(
        taskDefinition=task_desc["taskDefinitionArn"],
        startedBy=f"paaws-cli/shell/{get_email()}",
        overrides={
            "containerOverrides": [
                {
                    "name": task_desc["containerDefinitions"][0]["name"],
                    "command": command,
                }
            ]
        },
        **ecs_config["run_task_args"]
    )
    try:
        return resp["tasks"][0]
    except IndexError:
        Halo("Task failed to start").fail()
        print(f"Response:\n\t{resp}")
        return None



def formatted_time_ago(dt: datetime) -> str:
    ago = timeago.format(dt, datetime.datetime.now(datetime.timezone.utc))
    full = dt.isoformat(timespec="seconds")
    return colored(f"{full} ~ {ago}", attrs=["dark"])
