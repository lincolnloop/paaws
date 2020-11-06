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

# In order to create an HTTPS listener on the Load Balancer, we need a certificate.
# This certificate won't ever be used, but is needed to get everything setup.
# Normally you would never hard-code a certificate, but since this is never used
# to serve real traffic, it is ok.
DUMMY_CERT = {
    "key": """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDK4UKgnTCDzvre
ci2Tq5ffw58eZfTTyrrOk4Xpm/6jqykgAMKtaLN98CpRS5EeX3bUZYlM/yVXOZjv
EmhyhKEWt/goVHEQVno9YympLs3yRZbd2EekOXYWYNiBUw+5WX8Vubbrjyo48Ixq
V7Wx4ykSaREh+ymjtY7cJi4Frn1JHAXjbZMTGVuo/5MhDCRDXJL0NipP3OCgMTj3
sZGwjS7HIvdeHKS+pLHEQvpyGXNMnBlboR7Umu4rmqTLnlXCncCUgIqLL6yBC8ZU
Ibuy57W0mZDH8cpn1N2BUWaiQf2TgF9p2MG0+m5lKXUij8acMaD2IEATbazyL54p
9OA8gmLvAgMBAAECggEATOVkY4wwv0TMQVP1gmsffWif/t2WFlBYzcOMlibSNSbC
x6aCI0f0AF/vKjECKAj2+Toi+FQcyxrBpJvNitpKVFoWbPLUh+S/IFVdjQp4dMN7
k0pOnShKYeEDLsFUzGPnj0x80HvK/Rnvnr7v1yTKhHfeTorsFWjTZQ3zk6O3SOXx
AhVGlYotNx8/2DLc+IpujZgI8yBAfjXG4UCrVRhSanFZEQW/geEI5BQwAEwUBh1N
lZlUjRYcwhiQ5ZhPP52La8MJEcwyQoki9O1+mfPH7YMI4XbVG6LWl3gYUIcqw95b
uO1RD8IAQ4MFDy55IoB2L8/vdmgbY3+SKzEPVs+iAQKBgQD0x54UB47wd4gwRTyy
G5fRB3cihSCbrgDUsOTtd/Bw3XzOowNy3mlc88w6ShYnVHvekqWa4LUlO6h2Sx86
qyd+UfqYaRomFRi/w7ZkYrOd5R+zuyRiF9tBzAcDEPfh61WhMoLSDLatBJb4fY+p
mDUIces7ORQtV1WgVbY48AUxzwKBgQDULfd5/Jwd2AwMyflGq5vKVY0/PyOfE8NX
616b6r53zb4ymaMKt5RYovudPBaLg4f+PRR5lKSh2t3zfQVyEyAR2YA1B+TW0jtb
q4o4+m7w9tsA3k4KYQrRHEgAC/oZkH4vLUQwfcXGbqMNkJl2dhPr3kJiCS8vLmcA
Rid1qqek4QKBgQCaFFEwIHXcbhF++QY0wuO0gzN9ujkFZelF+LeRty7VjMX0OG6C
TvgZt6j1hA8f4LE8MCkoLYw5DK2FENJulq/8dtP8PiRklmEGzMYxuGOB32kuNH25
dXThnPFI/9RZFE7Jckcguzn9/OafMkJNKe8wCq1ckRhfVhsjGvDiNEvAxwKBgQC8
IzIgAWRwdgRhRqn5Butx4qAG57ZvNHfuum4+dEyFMHKorWBLfXJVkdbnmcMn2+42
+fPwxmOgfNB3OXEdsGWsTh6HZ0N7VBh79UPvt+etVEXmpDewrlGID7qsB/KwvlWV
AV9IXA2FIM8FlSTuTE7nw0E7aodjH5MHRC1zAWn7IQKBgQC2XahVBBE+0wTxoFdC
sb1+xIKlCmwi0wV03Wvn3wl5WJTFT/XwmyxFrqWKlJT3msf5AGQOagGfBfcm6zkE
gWRpTUF/2qG7+AXdfU98nWhx8EfR/FUwztPwlr5/Gv3fkUOpyjJp4Y3bOkpr+F/G
gCgwclDKh/He7BFAnih2JpDlUQ==
-----END PRIVATE KEY-----
""",
    "cert": """-----BEGIN CERTIFICATE-----
MIICzjCCAbYCCQDF/Pgr3R2J5jANBgkqhkiG9w0BAQsFADApMQswCQYDVQQGEwJV
UzEaMBgGA1UEAwwRcGFhd3MuZXhhbXBsZS5jb20wHhcNMjAwOTExMDM0OTQwWhcN
MjAxMjEwMDM0OTQwWjApMQswCQYDVQQGEwJVUzEaMBgGA1UEAwwRcGFhd3MuZXhh
bXBsZS5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDK4UKgnTCD
zvreci2Tq5ffw58eZfTTyrrOk4Xpm/6jqykgAMKtaLN98CpRS5EeX3bUZYlM/yVX
OZjvEmhyhKEWt/goVHEQVno9YympLs3yRZbd2EekOXYWYNiBUw+5WX8Vubbrjyo4
8IxqV7Wx4ykSaREh+ymjtY7cJi4Frn1JHAXjbZMTGVuo/5MhDCRDXJL0NipP3OCg
MTj3sZGwjS7HIvdeHKS+pLHEQvpyGXNMnBlboR7Umu4rmqTLnlXCncCUgIqLL6yB
C8ZUIbuy57W0mZDH8cpn1N2BUWaiQf2TgF9p2MG0+m5lKXUij8acMaD2IEATbazy
L54p9OA8gmLvAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAMP20NnEjOQfxEVhI6dP
yqZ8iD/RkDokfG63z4+JRNUR2zGeMas4r18Yb3jasKbJ0r8FYmvAv9+4R1yIvgBq
CCOQbPxWCSCIlovVtg3gH+fCHy1mPrNg+ixEIH6fNO1+TrNI8vPV+yIvF2N/5FI0
VguAtC/kXoWj6DfyBDBqvCUhqz4dPO37EgMELF+kA7OwsS6dpQ0TQf0VC14gAtRB
eDYfENBKn//znFmkfd2redFBhvrYAeYv0guiz9lwP292TaX3tV3EPhD5xkPXBMQr
icPcAI//mSAArzHF07eiGFdqX/WAqtbHzYTrbieQw2y+g3ut0clYcXgp9Cw0v8rf
aOE=
-----END CERTIFICATE-----
""",
}

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def _parameters(pyval: dict) -> List[dict]:
    return [{"ParameterKey": k, "ParameterValue": v} for k, v in pyval.items()]


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
        # certs can't be imported via cloudformation
        cert = boto3.client("acm").import_certificate(
            Certificate=DUMMY_CERT["cert"].encode(),
            PrivateKey=DUMMY_CERT["key"].encode(),
            Tags=tags + [{"Key": "Name", "Value": "paaws-dummy-cert"}],
        )
        cfn = cloudformation.create_stack(
            StackName="paaws-account",
            TemplateURL=ACCOUNT_FORMATION,
            Parameters=_parameters(
                {
                    "PaawsRoleExternalId": uuid.uuid4().hex,
                    "InitialCertificateArn": cert["CertificateArn"],
                }
            ),
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=tags,
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
    cfn = cloudformation.describe_stacks(StackName=cfn["StackId"])["Stacks"][0]
    if cfn["StackStatus"] != "CREATE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
        exit(1)
    with Halo(text="Generating keypair...", spinner="dots"):
        # generate a keypair for setting up EC2 instances
        # since we are connecting with SSM Session Manager, we don't need to
        # know what the key is
        boto3.client("ec2").create_key_pair(KeyName="paaws")
    Halo(text="done", text_color="green").succeed()


@create.command()
@click.option("--name", "-n", help="Name of cluster", default="paaws")
def cluster(name, dockerhub_username):
    """Create Paaws cluster"""
    ssm = boto3.client("ssm")
    try:
        ssm.get_parameter(Name=f"/paaws/cluster/{name}")
        Halo(text="Cluster already exists", text_color="red").fail()
        exit(1)
    except ssm.exceptions.ParameterNotFound:
        pass
    tags = [{"Key": "paaws:account", "Value": "true"}]
    region = boto3.session.Session().region_name
    stack_name = f"paaws-cluster-{name}"
    with Halo(text="Creating cluster:{name}...", spinner="dots"):
        cloudformation = boto3.client("cloudformation")
        cfn = cloudformation.create_stack(
            StackName=stack_name,
            TemplateURL=CLUSTER_FORMATION,
            Parameters=_parameters(
                {
                    "AvailabilityZones": [f"{region}a", f"{region}b", f"{region}c"],
                    "KeyPairName": "paaws",
                    "PaawsRoleExternalId": uuid.uuid4().hex,
                }
            ),
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=tags,
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(StackName=cfn["StackId"])
        stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
    if stack["StackStatus"] == "CREATE_COMPLETE":
        Halo(text="failed", text_color="red").fail()
    else:
        Halo(text="complete", text_color="green").succeed()
    # Cloudformation is missing some functionality. Cleanup after:
    # TODO: move to CustomResources in cloudformation
    with Halo(text="Cleaning up cluster...", spinner="dots"):
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}

        # Cleanup default Security Group
        vpc_id = outputs["VpcId"]
        ec2 = boto3.client("ec2")
        default_sg = ec2.describe_security_groups(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "group-name", "Values": ["default"]},
            ]
        )["SecurityGroups"][0]
        if default_sg["IpPermissions"]:
            ec2.revoke_security_group_ingress(
                GroupId=default_sg["GroupId"], IpPermissions=default_sg["IpPermissions"]
            )
        if default_sg["IpPermissionsEgress"]:
            ec2.revoke_security_group_egress(
                GroupId=default_sg["GroupId"],
                IpPermissions=default_sg["IpPermissionsEgress"],
            )

        autoscaling = boto3.client("autoscaling")
        # Update autoscaling
        autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=outputs["AutoScalingGroupName"],
            NewInstancesProtectedFromScaleIn=True,
        )
        autoscaling_group = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[outputs["AutoScalingGroupName"]]
        )["AutoScalingGroups"][0]
        instance_ids = [i["InstanceId"] for i in autoscaling_group["Instances"]]
        autoscaling.set_instance_protection(
            AutoScalingGroupName=outputs["AutoScalingGroupName"],
            ProtectedFromScaleIn=True,
            InstanceIds=instance_ids,
        )

        # Setup capacity provider
        ecs = boto3.client("ecs")
        cluster_ = ecs.describe_clusters(clusters=[outputs["EcsClusterName"]])[
            "clusters"
        ][0]
        if not cluster_["capacityProviders"]:
            capacity_provider = ecs.create_capacity_provider(
                name=name,
                autoScalingGroupProvider={
                    "autoScalingGroupArn": autoscaling_group["AutoScalingGroupARN"],
                    "managedScaling": {
                        "status": "ENABLED",
                        "targetCapacity": 100,
                        "minimumScalingStepSize": 1,
                        "maximumScalingStepSize": 1,
                    },
                    "managedTerminationProtection": "ENABLED",
                },
                tags=[{"key": t["Key"], "value": t["Value"]} for t in tags],
            )["capacityProvider"]
            ecs.put_cluster_capacity_providers(
                cluster=outputs["EcsClusterName"],
                capacityProviders=capacity_provider["name"],
                defaultCapacityProviderStrategy=[
                    {
                        "capacityProvider": capacity_provider["name"],
                        "weight": 100,
                        "base": 0,
                    }
                ],
            )
    Halo(text="complete", text_color="green").succeed()


@create.command()
@click.option("--name", "-n", help="Name of app")
@click.option("--cluster-name", "-c", default="paaws", help="Cluster to deploy to")
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
    try:
        cluster_stack_id = json.loads(
            ssm.get_parameter(Name=f"/paaws/cluster/{cluster_name}")["Parameter"][
                "Value"
            ]
        )["stack_id"]
    except ssm.exceptions.ParameterNotFound:
        fail("Cluster does not exist")
    # TODO make this more robust for GH enterprise and support CODECOMMIT as a fallback
    if "github.com" in repository_url:
        repository_type = "GITHUB"
    elif "bitbucket.org" in repository_url:
        repository_type = "BITBUCKET"
    else:
        raise RuntimeError("Unsupported repository type")
    cloudformation = boto3.client("cloudformation")
    outputs = _stack_outputs(cloudformation, cluster_stack_id)
    cluster_parameters = {
        k: outputs[k]
        for k in [
            "EcsClusterArn",
            "EcsClusterName",
            "LoadBalancerArn",
            "LoadBalancerListenerArn",
            "LoadBalancerSuffix",
            "PublicSubnetIds",
            "VpcId",
        ]
    }
    ecs = boto3.client("ecs")
    cluster_parameters["CapacityProviderName"] = ecs.describe_clusters(
        clusters=[outputs["EcsClusterName"]]
    )["clusters"][0]["capacityProviders"][0]
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
