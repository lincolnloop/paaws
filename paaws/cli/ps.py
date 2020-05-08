from collections import defaultdict

import boto3
import click
from halo import Halo
from termcolor import colored, cprint

from ..app import app
from ..utils import formatted_time_ago


def task_id(task_detail: dict) -> str:
    tags = {t["key"]: t["value"] for t in task_detail["tags"]}
    try:
        return tags["paaws:buildNumber"]
    except KeyError:
        return task_detail["taskArn"].split("/")[-1]


@click.command()
def ps():
    """Show running containers"""
    ecs = boto3.client("ecs")
    with Halo(text="fetching container information", spinner="dots"):
        tasks = app.get_tasks()
        tasks_by_group = defaultdict(list)
        task_definitions = {}
        for t in tasks:
            tasks_by_group[t["group"]].append(t)
            if t["taskDefinitionArn"] not in task_definitions:
                task_definitions[t["taskDefinitionArn"]] = ecs.describe_task_definition(
                    taskDefinition=t["taskDefinitionArn"]
                )["taskDefinition"]
    for group in sorted(tasks_by_group.keys()):
        tasks = tasks_by_group[group]
        defn = task_definitions[tasks[0]["taskDefinitionArn"]]
        print(colored("===", attrs=["dark"]), colored(group, "green"))
        for t in tasks:
            task_line = [
                task_id(t),
                " ",
                colored("(", "white"),
                colored(
                    "cpu:{cpu} mem:{memory}".format(
                        cpu=int(t["cpu"]) / 1024, memory=t["memory"]
                    ),
                    "blue",
                    attrs=["dark", "bold"],
                ),
                colored(")", "white"),
                ": ",
                t["lastStatus"].lower(),
                " ",
            ]
            if "startedAt" in t:
                task_line.append(formatted_time_ago(t["startedAt"]))
            print("".join(task_line))
            for c in t["containers"]:
                try:
                    command = [
                        o["command"]
                        for o in t["overrides"]["containerOverrides"]
                        if o["name"] == c["name"]
                    ][0]
                except (KeyError, IndexError):
                    command = [
                        cd.get("command", ["[container default cmd]"])
                        for cd in defn["containerDefinitions"]
                        if cd["name"] == c["name"]
                    ][0]
                print_name = f"  {c['name']}:"
                indent = len(print_name) + 1
                print(print_name, colored(" ".join(command), "white"))
                container_line2 = [
                    " " * indent,
                    "{image} {status}".format(
                        image=c["image"].split("/")[-1], status=c["lastStatus"].lower()
                    ),
                ]
                cprint("".join(container_line2), attrs=["dark"])
        print("")
