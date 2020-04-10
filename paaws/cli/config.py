from typing import Dict

from halo import Halo

import boto3
import click
from termcolor import colored

from ..app import app
from ..utils import halo_success


@Halo(text="fetching parameters", spinner="dots")
def load_parameters(path, next_token=None) -> Dict[str, str]:
    """Fetch values from AWS Parameter Store"""
    ssm = boto3.client("ssm")
    # allow lookups when IAM only allows {arn}/*
    if not path.endswith("/"):
        path += "/"
    kwargs = {"Path": path, "WithDecryption": True}
    if next_token:
        kwargs.update({"NextToken": next_token})
    results = ssm.get_parameters_by_path(**kwargs)
    parameters = {
        p["Name"][len(path) :].upper(): p["Value"] for p in results["Parameters"]
    }
    if "NextToken" in results:
        parameters.update(load_parameters(path, results["NextToken"]))
    return parameters


@click.group()
def config():
    """View/edit environment variables"""
    pass


@config.command("list")
def list_() -> None:
    """Environment variables for applications"""
    print(
        colored("===", attrs=["dark"]),
        colored(f"{app.name} Config Vars", "white", attrs=["bold"]),
    )
    parameters = load_parameters(app.parameter_prefix)
    cell_width = max([len(k) for k in parameters.keys()])
    for k in sorted(load_parameters(f"/{app.name}").keys()):
        print(
            colored(
                "{0: <{width}}".format(k.lstrip("/") + ":", width=cell_width), "green"
            ),
            parameters[k],
        )


@config.command()
@click.argument("key")
def get(key: str) -> None:
    """Get the value for a variable"""
    ssm = boto3.client("ssm")
    name = "/".join([app.parameter_prefix, key.lower()])
    print(ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"])


@config.command()
@click.argument("key_val")
def set(key_val: str) -> None:
    """Get the value for a variable"""
    key, val = key_val.split("=", 1)
    ssm = boto3.client("ssm")
    name = "/".join([app.parameter_prefix, key.lower()])
    with halo_success(text=f"setting parameter {key.upper()}"):
        ssm.put_parameter(Name=name, Value=val, Type="SecureString", Overwrite=True)


@config.command()
@click.argument("key")
def unset(key: str) -> None:
    """Unset (delete) a variable"""
    ssm = boto3.client("ssm")
    name = "/".join([app.parameter_prefix, key.lower()])
    with halo_success(text=f"deleting parameter {key.upper()}"):
        ssm.delete_parameter(Name=name)
