import time

import boto3
import click
from blessed import Terminal
from halo import Halo
from termcolor import colored

from ..app import app
from ..utils import formatted_time_ago


def deployment_id(detail: dict) -> str:
    ecs = boto3.client("ecs")
    resp = ecs.describe_task_definition(
        taskDefinition=detail["taskDefinition"], include=["TAGS"]
    )
    try:
        return [t for t in resp["tags"] if t["key"] == "paaws:buildNumber"][0]["value"]
    except IndexError:
        return detail["taskDefinition"].split("/")[-1]


def _deployment_line(deployment: dict) -> str:
    color_map = {
        "PRIMARY": "green",
        "ACTIVE": "yellow",
    }
    line = [
        deployment_id(deployment),
        ": ",
        colored(deployment["status"].lower(), color_map.get(deployment["status"], "")),
        colored(" tasks:{runningCount}".format(**deployment), "white"),
    ]
    if deployment["runningCount"] != deployment["desiredCount"]:
        line.append(
            colored(
                " desired:{desiredCount} pending:{pendingCount}".format(**deployment),
                "yellow",
            )
        )
    line.append(" " + formatted_time_ago(deployment["createdAt"]))
    return "".join(line)


def _service_status_lines(service):
    return (
        [colored("=== ", attrs=["dark"]) + colored(service["serviceName"], "green")]
        + [_deployment_line(d) for d in service["deployments"]]
        + [""]
    )


@click.command()
@click.option("--watch", "-w", default=False, is_flag=True)
def deployments(watch):
    """List deployments"""
    if watch:
        return _watch_deployment()
    with Halo(text="fetching deployments", spinner="dots"):
        services = app.get_services()

    for service in services:
        print("\n".join(_service_status_lines(service)))


def _watch_deployment():
    with Halo(text="fetching deployments", spinner="dots"):
        services = app.get_services()
    ready = [False for s in services]
    term = Terminal()
    height = 0
    refresh_interval = 5
    while True:
        text = []
        for idx, service in enumerate(services):
            text.extend(_service_status_lines(service))
            if len(service["deployments"]) == 1:
                ready[idx] = True
        # clear screen
        if height:
            print(term.move_up(height) + term.clear_eos)
        print("\n".join(text))
        if all(ready):
            break
        print("")
        for i in range(refresh_interval):
            print(
                term.move_up()
                + colored(
                    f"next update in {refresh_interval - i} seconds", attrs=["dark"]
                )
            )
            time.sleep(1)

        height = len(text) + 2
        services = app.get_services()
    Halo(text="ready", text_color="green").succeed()
