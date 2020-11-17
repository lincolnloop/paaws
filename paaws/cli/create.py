import os
import json
import random
import uuid
from typing import List

import boto3
import click
from halo import Halo
from paaws.utils import fail

APP_FORMATION = "https://s3.amazonaws.com/paaws-cloudformations/latest/app.json"
CLUSTER_FORMATION = "https://s3.amazonaws.com/paaws-cloudformations/latest/cluster.json"
ACCOUNT_FORMATION = "https://s3.amazonaws.com/paaws-cloudformations/latest/account.json"
DATABASE_FORMATION = (
    "https://s3.amazonaws.com/paaws-cloudformations/latest/database.json"
)

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def _parameters(pyval: dict) -> List[dict]:
    return [{"ParameterKey": k, "ParameterValue": v} for k, v in pyval.items()]



def _stack_outputs_from_parameter(cloudformation, ssm, parameter_name: str) -> dict:
    try:
        cluster_stack_id = json.loads(
            ssm.get_parameter(Name=parameter_name)["Parameter"][
                "Value"
            ]
        )["stack_id"]
    except ssm.exceptions.ParameterNotFound:
        fail(f"{parameter_name} does not exist")
    return _stack_outputs(cloudformation, cluster_stack_id)


def _stack_outputs(cloudformation, stack_id: str) -> dict:
    stack = cloudformation.describe_stacks(StackName=stack_id)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}


@click.group()
def create():
    pass


@create.command()
@click.option(
    "--dockerhub-username", help="User for pulling public images from DockerHub"
)
@click.option(
    "--dockerhub-access-token",
    help="Access token for DockerHub. Generate at https://hub.docker.com/settings/security",
    hide_input=True,
    prompt=True,
)
def account(dockerhub_username, dockerhub_access_token):
    """Create account-level Paaws resources. Requires a Docker Hub account and access token"""
    ssm = boto3.client("ssm")
    cloudformation = boto3.client("cloudformation")
    try:
        ssm.get_parameter(Name="/paaws/account")
        Halo(text="Account already exists", text_color="red").fail()
        exit(1)
    except ssm.exceptions.ParameterNotFound:
        pass
    tags = [{"Key": "paaws:account", "Value": "true"}]
    with Halo(text="Creating account-level resources...", spinner="dots"):
        # Can't create secure parameters from Cloudformation
        ssm.put_parameter(
            Name="/paaws/account/dockerhub-username",
            Value=dockerhub_username,
            Type="SecureString",
            Tags=tags,
        )
        ssm.put_parameter(
            Name="/paaws/account/dockerhub-access-token",
            Value=dockerhub_access_token,
            Type="SecureString",
            Tags=tags,
        )

        cfn = cloudformation.create_stack(
            StackName="paaws-account",
            TemplateURL=ACCOUNT_FORMATION,
            Parameters=_parameters(
                {
                    "PaawsRoleExternalId": uuid.uuid4().hex,
                }
            ),
            Capabilities=["CAPABILITY_IAM"],
            Tags=tags,
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
    cfn = cloudformation.describe_stacks(StackName=cfn["StackId"])["Stacks"][0]
    if cfn["StackStatus"] != "CREATE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    Halo(text="done", text_color="green").succeed()


@create.command()
@click.argument("name", default="paaws")
@click.option("--domain", "-d", help="Parent domain for apps in the cluster")
# TODO: lookup the hosted zone id based on the domain
@click.option("--hosted-zone-id", "-z", help="AWS Route53 Hosted Zone ID for domain.")
def cluster(name: str, domain: str, hosted_zone_id: str):
    """Create Paaws cluster"""
    ssm = boto3.client("ssm")
    try:
        ssm.get_parameter(Name=f"/paaws/cluster/{name}")
        Halo(text="Cluster already exists", text_color="red").fail()
        exit(1)
    except ssm.exceptions.ParameterNotFound:
        pass
    tags = [{"Key": "paaws", "Value": "true"}, {"Key": "paaws:cluster", "Value": name}]
    region = boto3.session.Session().region_name
    stack_name = f"paaws-cluster-{name}"
    with Halo(text=f"Creating cluster:{name}...", spinner="dots"):
        cloudformation = boto3.client("cloudformation")
        account_outputs = _stack_outputs_from_parameter(cloudformation, ssm, "/paaws/account")
        cfn = cloudformation.create_stack(
            StackName=stack_name,
            TemplateURL=CLUSTER_FORMATION,
            Parameters=_parameters(
                {
                    "Name": name,
                    "AvailabilityZones": ",".join([f"{region}a", f"{region}b", f"{region}c"]),
                    "KeyPairName": account_outputs["KeyPairName"],
                    "Domain": domain,
                    "HostedZone": hosted_zone_id
                }
            ),
            Capabilities=["CAPABILITY_IAM"],
            Tags=tags,
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
        stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
    if stack["StackStatus"] != "CREATE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
    else:
        Halo(text="complete", text_color="green").succeed()


@create.command()
@click.option("--name", "-n", help="Name of database")
@click.option("--cluster", "-c", default="paaws", help="Cluster to deploy to")
@click.option("--instance-class", "-i", default="db.t3.medium", help="Database size")
@click.option(
    "--multi-az",
    "-m",
    is_flag=True,
    help="Run database in multiple availability zones. Doubles the cost, but provides better availability.",
)
def database(name, cluster, instance_class, multi_az):
    """Create database within a cluster"""
    # TODO: lookup cluster data and run formation
    pass


@create.command()
@click.option("--name", "-n", help="Name of app")
@click.option("--cluster", "-c", default="paaws", help="Cluster to deploy to")
@click.option(
    "--repository-url",
    "-r",
    help="e.g., https://github.com/lincolnloop/lincolnloop.git",
)
@click.option("--branch", "-b", prompt=True, help="Branch to build/deploy from")
@click.option(
    "--addon-private-s3",
    is_flag=True,
    help="Include a private S3 bucket addon",
)
@click.option(
    "--addon-public-s3",
    is_flag=True,
    help="Include a public S3 bucket addon",
)
@click.option(
    "--addon-database",
    help="Create a database on the provided cluster",
)
@click.option(
    "--addon-sqs",
    is_flag=True,
    help="Create an SQS queue",
)
@click.option(
    "--addon-ses-domain",
    help="Domain to allow outbound email via SES (requires SES Domain Identity is already setup)",
)
@click.option(
    "--healthcheck-path",
    help="Path that will always response with a 200 status code when the app is ready, e.g. /-/health/",
)
@click.option("--domain", help="Route traffic from this domain to the app")
@click.option(
    "--users",
    help="Comma-separated list of email addresses of users that can manage the app",
)
def app(
    name,
    cluster_name,
    repository_url,
    branch,
    addon_private_s3,
    addon_public_s3,
    addon_database,
    addon_sqs,
    addon_ses_domain,
    healthcheck_path,
    domain,
    users,
):
    """Create Paaws app"""
    ssm = boto3.client("ssm")
    try:
        ssm.get_parameter(Name=f"/paaws/apps/{name}/settings")
        fail("App already exists")
    except ssm.exceptions.ParameterNotFound:
        pass
    # TODO make this more robust for GH enterprise and support CODECOMMIT as a fallback
    if "github.com" in repository_url:
        repository_type = "GITHUB"
    elif "bitbucket.org" in repository_url:
        repository_type = "BITBUCKET"
    else:
        raise RuntimeError("Unsupported repository type")
    cloudformation = boto3.client("cloudformation")
    outputs = _stack_outputs(cloudformation, ssm, f"/paaws/cluster/{cluster_name}")
    cluster_parameters = {
        k: outputs[k]
        for k in [
            "CapacityProviderName",
            "EcsClusterArn",
            "EcsClusterName",
            "LoadBalancerArn",
            "LoadBalancerListenerArn",
            "LoadBalancerSuffix",
            "PublicSubnetIds",
            "VpcId",
        ]
    }
    domains = [f"{name}.{outputs['Domain']}"]
    if domain:
        domains.append(domain)
    parameters = {
        "Branch": branch,
        "Domains": ",".join(domains),
        "HealthCheckPath": healthcheck_path,
        "LoadBalancerRulePriority": str(
            random.choice(range(1, 50001))
        ),  # TODO: verify empty slot
        "Name": name,
        "PaawsRoleExternalId": uuid.uuid4().hex,
        "PrivateS3BucketEnabled": "enabled" if addon_private_s3 else "disabled",
        "PublicS3BucketEnabled": "enabled" if addon_public_s3 else "disabled",
        "SesDomain": addon_ses_domain or "",
        "SQSQueueEnabled": "enabled" if addon_sqs else "disabled",
        "RepositoryType": repository_type,
        "RepositoryUrl": repository_url,
        "Type": "app",
        "AllowedUsers": users,
        **cluster_parameters,
    }
    if addon_database:
        db_cluster = json.loads(
            ssm.get_parameter(Name=f"/paaws/database/{addon_database}")["Parameter"][
                "Value"
            ]
        )
        if db_cluster["vpc_id"] != cluster_parameters["VpcId"]:
            fail(
                "\n".join(
                    [
                        "Database is not in the same cluster as application.",
                        f"  Database VPC: {db_cluster['vpc_id']}",
                        f"  Application VPC: {cluster_parameters['VpcId']}",
                    ]
                )
            )
        parameters["DatabaseManagementLambdaArn"] = db_cluster["management_lambda_arn"]
    else:
        parameters["DatabaseManagementLambdaArn"] = ""
    with Halo(text="Creating application resources...", spinner="dots"):
        cfn = cloudformation.create_stack(
            StackName=f"paaws-app-{name}",
            TemplateURL=APP_FORMATION,
            Parameters=_parameters(parameters),
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=[
                {"Key": k, "Value": v}
                for k, v in {
                    "paaws:appName": name,
                    "paaws:cluster": outputs["EcsClusterName"],
                    "paaws": "true",
                }.items()
            ],
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
    cfn = cloudformation.describe_stacks(StackName=cfn["StackId"])["Stacks"][0]
    if cfn["StackStatus"] != "CREATE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    Halo(text="done", text_color="green").succeed()
