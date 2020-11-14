import os
from urllib.parse import quote

import boto3
import click
from halo import Halo
from paaws.utils import fail

from paaws.cli.create import APP_FORMATION, ACCOUNT_FORMATION, CLUSTER_FORMATION

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@click.group()
def upgrade():
    pass

def _update_stack(stack_name: str, template: str) -> dict:
    cloudformation = boto3.client("cloudformation")
    stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
    cfn = cloudformation.update_stack(
        StackName=stack_name,
        TemplateURL=template,
        Parameters=stack["Parameters"],
        Capabilities=["CAPABILITY_IAM"]
    )
    waiter = cloudformation.get_waiter("stack_update_complete")
    waiter.wait(StackName=cfn["StackId"])
    stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
    if stack["StackStatus"] != "UPDATE_COMPLETE":
        url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/events?stackId={quote(cfn['StackId'])}"
        fail(f"Update failed. See {url} for details.")
    Halo(text="complete", text_color="green").succeed()
    return stack


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
@click.argument("app_name")
def app(app_name):
    """Updates the Cloudformation stack for the given app"""
    stack_name = f"paaws-app-{app_name}"
    with Halo(text=f"Upgrading app:{app_name} stack...", spinner="dots"):
        _update_stack(stack_name, template=APP_FORMATION)

