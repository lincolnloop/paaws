import os
import json
import random
import uuid
import time
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

def _create_stack(cloudformation, kwargs: dict, is_change_set: bool = False) -> dict:

    if is_change_set:
        cfn = cloudformation.create_change_set(
            ChangeSetType="CREATE",
            ChangeSetName=f"create-{int(time.time())}",
            **kwargs,
        )
        waiter = cloudformation.get_waiter("change_set_create_complete")
        waiter.wait(ChangeSetName=cfn["Id"], StackName=cfn["StackId"])
        resp = cloudformation.describe_change_set(
            ChangeSetName=cfn["Id"], StackName=cfn["StackId"]
        )
    else:
        cfn = cloudformation.create_stack(**kwargs)
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
        resp = cloudformation.describe_stacks(StackName=cfn["StackName"])["Stacks"][0]
        if resp["StackStatus"] != "CREATE_COMPLETE":
            url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/events?stackId={quote(cfn['StackId'])}"
            fail(f"Create failed. See {url} for details.")
    Halo(text="complete", text_color="green").succeed()
    if is_change_set:
        url = f"https://console.aws.amazon.com/cloudformation/home#/stacks/changesets/changes?stackId={resp['StackId']}&changeSetId={resp['ChangeSetId']}"
        print("View and approve the change set at:")
        print(f"  {url}")
    return resp


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
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
)
def account(dockerhub_username, dockerhub_access_token, check: bool):
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
    if check:
        msg = "Creating Cloudformation Change Set for account-level resources..."
    else:
        msg = "Creating account-level resources..."
    with Halo(text=msg, spinner="dots"):
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
        _create_stack(
            cloudformation,
            dict(
                StackName="paaws-account",
                TemplateURL=ACCOUNT_FORMATION,
                Parameters=_parameters({"PaawsRoleExternalId": uuid.uuid4().hex}),
                Capabilities=["CAPABILITY_IAM"],
                Tags=tags,
            ),
            is_change_set=check)


@create.command()
@click.argument("name", default="paaws")
@click.option("--domain", "-d", help="Parent domain for apps in the cluster")
# TODO: lookup the hosted zone id based on the domain
@click.option("--hosted-zone-id", "-z", help="AWS Route53 Hosted Zone ID for domain.")
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
)
def cluster(name: str, domain: str, hosted_zone_id: str, check: bool):
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
    if check:
        msg = f"Creating Cloudformation Change Set for cluster:{name} resources..."
    else:
        msg = f"Creating cluster:{name}..."
    with Halo(text=msg, spinner="dots"):
        cloudformation = boto3.client("cloudformation")
        account_outputs = _stack_outputs_from_parameter(cloudformation, ssm, "/paaws/account")
        _create_stack(
            cloudformation,
            dict(
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
            ),
            is_change_set=check
        )


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
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
)
def database(name, cluster, instance_class, multi_az, check: bool):
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
@click.option(
    "--check",
    "-c",
    is_flag=True,
    default=False,
    help="Review changes prior to applying",
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
    check: bool
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
    if check:
        msg = f"Creating Cloudformation Change Set for app:{name} resources..."
    else:
        msg = f"Creating app:{name} resources..."
    with Halo(text=msg, spinner="dots"):
        _create_stack(
            cloudformation,
            dict(
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
            ),
            is_change_set=check
        )
