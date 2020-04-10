"""App name state and configuration for resources"""
import json
from functools import wraps
from typing import List, Optional

import boto3
from botocore.client import ClientError

from .utils import tags_match


class NoApplicationDefined(Exception):
    pass


def requires_appname(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.name:
            raise NoApplicationDefined()
        return func(self, *args, **kwargs)

    return wrapper


class Application:
    name: str
    cluster: str
    log_group: str
    parameter_prefix: str
    shell_service: str
    tags: List[dict]

    def _load_config(self) -> dict:
        """Load any configuration for app from parameter store"""
        config_parameter_name = f"/paaws/apps/{self.name}"
        ssm = boto3.client("ssm")

        try:
            return json.loads(
                ssm.get_parameter(Name=config_parameter_name)["Parameter"]["Value"]
            )
        except ssm.exceptions.ParameterNotFound:
            pass
        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                pass
        return {}

    def _define_resources(self) -> None:
        """Set attributes for resources on this app"""
        if not self.name:
            raise NoApplicationDefined()
        defaults = {
            "cluster": self.name,
            "log_group": self.name,
            "shell_service": f"{self.name}-debug",
            "parameter_prefix": f"/{self.name}",
            "tags": [],
        }
        defaults.update(self._load_config())
        for k, v in defaults.items():
            setattr(self, k, v)

    def setup(self, name: str) -> None:
        """Update resources when name is set"""
        self.name = name
        self._define_resources()

    @requires_appname
    def get_tasks(self) -> List[dict]:
        """List of task descriptions for app"""
        ecs = boto3.client("ecs")
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
        ecs = boto3.client("ecs")
        service_arns = ecs.list_services(cluster=app.cluster)["serviceArns"]
        return [
            s
            for s in ecs.describe_services(
                cluster=app.cluster, services=service_arns, include=["TAGS"]
            )["services"]
            if tags_match(s.get("tags", []), app.tags)
        ]

    @requires_appname
    def get_shell_task_definition(self) -> dict:
        """Get task definition from shell service"""
        try:
            service = [
                s for s in self.get_services() if s["serviceName"] == self.shell_service
            ][0]
        except IndexError:
            raise Exception(f"Shell service '{app.shell_service}' does not exist")
        return service["taskDefinition"]


app = Application()
