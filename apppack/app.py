"""App name state and configuration for resources"""
import json
from functools import wraps, lru_cache
from typing import List

import boto3
from botocore.client import ClientError

from .cli.auth import get_credentials
from .utils import tags_match, replace_decimals


class NoApplicationDefined(Exception):
    pass


def requires_appname(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.name:
            raise NoApplicationDefined()
        return func(self, *args, **kwargs)

    return wrapper


def merge(source: dict, destination: dict) -> dict:
    """
    Perform a "deep" merge of the two dictionaries
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination


class Application:
    name: str
    cluster: str
    codebuild_project: str
    log_group: str
    parameter_prefix: str
    shell_service: str
    tags: List[dict]

    def _initialize_settings(self) -> None:
        """Set attributes for resources on this app"""
        if not self.name:
            raise NoApplicationDefined()
        default_settings = {
            "cluster": {"name": self.name},
            "log_group": {"name": self.name},
            "parameter_store": {"prefix": f"/{self.name}", "chamber_compatible": False},
            "codebuild_project": {"name": self.name},
            "shell": {"task_family": f"{self.name}-shell", "command": "bash -l",},
            "db_utils": {
                "shell_task_family": f"{self.name}-dbutils-shell",
                "dumpload_task_family": f"{self.name}-dbutils-dumpload",
                "s3_bucket": f"{self.name}-dbutils",
            },
            "tags": [],
        }

        self.settings = merge(self.dynamodb_item("settings"), default_settings)

    def setup(self, name: str) -> None:
        """Update resources when name is set"""
        self.name = name
        self._initialize_settings()

    @property
    def cluster(self) -> str:
        return self.settings["cluster"]["name"]

    @property
    def tags(self) -> List[dict]:
        return self.settings["tags"]

    @property
    def log_group(self) -> str:
        return self.settings["log_group"]["name"]

    @property
    def parameter_prefix(self) -> str:
        return self.settings["parameter_store"]["prefix"]

    @property
    def chamber_compatible_config(self) -> bool:
        return self.settings["parameter_store"]["chamber_compatible"]

    @lru_cache(maxsize=16)
    def boto3_client(self, client: str):
        """Get boto3 client with credentials for the app"""
        creds = get_credentials(self.name)
        return boto3.client(
            client,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    @lru_cache(maxsize=16)
    def boto3_resource(self, resource: str):
        """Get boto3 client with credentials for the app"""
        creds = get_credentials(self.name)
        return boto3.resource(
            resource,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    def dynamodb_item(self, name: str):
        return replace_decimals(self.boto3_resource("dynamodb").Table("paaws").get_item(
            Key={"primary_id": f"APP#{self.name}", "secondary_id": name}
        )["Item"]["value"])


    @requires_appname
    def get_tasks(self) -> List[dict]:
        """List of task descriptions for app"""
        ecs = self.boto3_client("ecs")
        task_arns = ecs.list_tasks(cluster=self.cluster)["taskArns"]
        return [
            t
            for t in ecs.describe_tasks(
                cluster=self.cluster, tasks=task_arns, include=["TAGS"]
            )["tasks"]
            if tags_match(t.get("tags", []), self.tags)
        ]

    @requires_appname
    def get_services(self) -> List[dict]:
        """List of service descriptions for app"""
        ecs = self.boto3_client("ecs")
        service_arns = ecs.list_services(cluster=self.cluster)["serviceArns"]
        return [
            s
            for s in ecs.describe_services(
                cluster=self.cluster, services=service_arns, include=["TAGS"]
            )["services"]
            if tags_match(s.get("tags", []), self.tags)
        ]

    @requires_appname
    def get_builds(self, limit=20):
        codebuild = self.boto3_client("codebuild")
        return codebuild.batch_get_builds(
            ids=codebuild.list_builds_for_project(
                projectName=self.settings["codebuild_project"]["name"]
            )["ids"][:limit]
        )["builds"]


app = Application()
