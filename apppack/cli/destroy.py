import json

import boto3
import click
from halo import Halo
from termcolor import cprint

cloudformation = boto3.client("cloudformation")
ssm = boto3.client("cloudformation")
autoscaling = boto3.client("autoscaling")
ecs = boto3.client("ecs")
ec2 = boto3.client("ec2")


@click.group()
def destroy():
    pass


@destroy.command
def account():
    cprint(
        "This will destroy the account-level resources for Paaws. Are you sure you want to continue?",
        "red",
    )
    if input('type "destroy" to continue') != "destroy":
        exit(0)
    stack_id = json.loads(
        ssm.get_parameter(Name="/paaws/account")["Parameter"]["Value"]
    )["stack_id"]
    with Halo(text="Destroying Paaws account...", spinner="dots"):
        cloudformation.delete_stack(StackName=stack_id)
        waiter = cloudformation.get_waiter("stack_delete_complete")
        waiter.wait(StackName=stack_id)
        cfn = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
    if cfn["StackStatus"] != "DELETE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    Halo(text="destroyed", text_color="green").succeed()


@destroy.command
@click.argument("name")
def cluster(name):
    stack_id = json.loads(
        ssm.get_parameter(Name=f"/paaws/cluster/{name}")["Parameter"]["Value"]
    )["stack_id"]
    cprint(
        f'This will destroy the Paaws cluster "{name}". Are you sure you want to continue?',
        "red",
    )
    if input('type "destroy" to continue') != "destroy":
        exit(0)

    with Halo(text=f'Destroying cluster "{name}"...', spinner="dots"):
        stack = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}

        # terminate EC2 instances
        autoscaling_group = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[outputs["AutoScalingGroupName"]]
        )["AutoScalingGroups"][0]
        for instance in autoscaling_group["Instances"]:
            autoscaling.terminate_instance_in_auto_scaling_group(
                InstanceId=instance["InstanceId"], ShouldDecrementDesiredCapacity=True
            )
        capacity_provider = ecs.describe_clusters(clusters=[outputs["EcsClusterName"]])[
            "clusters"
        ][0]["capacityProvider"]

        cloudformation.delete_stack(StackName=stack_id)
        waiter = cloudformation.get_waiter("stack_delete_complete")
        waiter.wait(StackName=stack_id)
        cfn = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
    if cfn["StackStatus"] != "DELETE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    ecs.destroy_capacity_provider(capacityProvider=capacity_provider)
    Halo(text="destroyed", text_color="green").succeed()


@destroy.command
@click.argument("name")
def app(name):
    stack_id = boto3.resource("dynamodb").Table("paaws").get_item(
        Key={"primary_id": f"APP#{name}", "secondary_id": "settings"}
    )["Item]["value"]["stack_id"]
    cprint(
        f'This will destroy the Paaws app "{name}". Are you sure you want to continue?',
        "red",
    )
    if input('type "destroy" to continue') != "destroy":
        exit(0)

    with Halo(text=f'Destroying cluster "{name}"...', spinner="dots"):
        stack = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
        # TODO: destroy services, config vars, scheduled tasks, etc... use orchestrator?

        cloudformation.delete_stack(StackName=stack_id)
        waiter = cloudformation.get_waiter("stack_delete_complete")
        waiter.wait(StackName=stack_id)
        cfn = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
    if cfn["StackStatus"] != "DELETE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    Halo(text="destroyed", text_color="green").succeed()
