import os
import time
from urllib.parse import quote

import boto3
import click
from halo import Halo
from paaws.utils import fail

from paaws.cli.create import (
    APP_FORMATION,
    ACCOUNT_FORMATION,
    CLUSTER_FORMATION,
    DATABASE_FORMATION,
)

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@click.group()
def upgrade():
    pass


def _update_stack(stack_name: str, template: str, is_change_set: bool = False) -> dict:
    cloudformation = boto3.client("cloudformation")
    stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
    kwargs = dict(
        StackName=stack_name,
        TemplateURL=template,
        Parameters=stack["Parameters"],
        Capabilities=["CAPABILITY_IAM"],
    )
    if is_change_set:
        cfn = cloudformation.create_change_set(
            ChangeSetType="UPDATE",
            ChangeSetName=f"upgrade-{int(time.time())}",
            **kwargs,
        )
        waiter = cloudformation.get_waiter("change_set_create_complete")
        waiter.wait(ChangeSetName=cfn["Id"], StackName=cfn["StackId"])
        resp = cloudformation.describe_change_set(
            ChangeSetName=cfn["Id"], StackName=cfn["StackId"]
        )
    else:
        cfn = cloudformation.update_stack(**kwargs)
        waiter = cloudformation.get_waiter("stack_update_complete")
        waiter.wait(StackName=cfn["StackId"])
        resp = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
        if resp["StackStatus"] != "UPDATE_COMPLETE":
            url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/events?stackId={quote(cfn['StackId'])}"
            fail(f"Update failed. See {url} for details.")
    Halo(text="complete", text_color="green").succeed()
    return resp


@upgrade.command()
def account():
    """Updates the Cloudformation stack for the given app"""
    stack_name = "paaws-account"
    with Halo(text="Upgrading account stack...", spinner="dots"):
        _update_stack(stack_name, template=ACCOUNT_FORMATION)


@upgrade.command()
@click.argument("name", default="paaws")
def cluster(name):
    """Updates the Cloudformation stack for the given app"""
    stack_name = f"paaws-cluster-{name}"
    with Halo(text=f"Upgrading cluster:{name} stack...", spinner="dots"):
        _update_stack(stack_name, template=CLUSTER_FORMATION)


@upgrade.command()
@click.argument("name")
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
)
def database(name: str, check: bool):
    """Updates the Cloudformation stack for the given database"""
    stack_name = f"paaws-database-{name}"
    if check:
        msg = f"Creating change set for upgrade of database:{name} stack..."
    else:
        msg = f"Upgrading database:{name} stack..."
    with Halo(text=msg, spinner="dots"):
        resp = _update_stack(
            stack_name, template=DATABASE_FORMATION, is_change_set=check
        )
    if check:
        url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/changesets/changes?stackId={resp['StackId']}&changeSetId={resp['ChangeSetId']}"
        print("View and approve the change set at:")
        print(f"  {url}")


@upgrade.command()
@click.argument("app_name")
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
)
def app(app_name, check: bool):
    """Updates the Cloudformation stack for the given app"""
    stack_name = f"paaws-app-{app_name}"
    if check:
        msg = f"Creating change set for upgrade of app:{app_name} stack..."
    else:
        msg = f"Upgrading app:{app_name} stack..."
    with Halo(text=msg, spinner="dots"):
        resp = _update_stack(stack_name, template=APP_FORMATION, is_change_set=check)
    if check:
        url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/changesets/changes?stackId={quote(resp['StackId'])}&changeSetId={quote(resp['ChangeSetId'])}"
        print("View and approve the change set at:")
        print(f"  {url}")
