from halo import Halo

import boto3
import click
from termcolor import colored

from ..app import app
from ..utils import halo_success, load_parameters


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
    with Halo(text="fetching parameters", spinner="dots"):
        parameters = load_parameters(app.parameter_prefix)
        if app.chamber_compatible_config:
            parameters = {k.upper(): v for k, v in parameters.items()}
    cell_width = max([len(k) for k in parameters.keys()]) + 1
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
    if app.chamber_compatible_config:
        key = key.lower()
    name = "/".join([app.parameter_prefix, key])
    print(ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"])


@config.command()
@click.argument("key_val")
def set(key_val: str) -> None:
    """Set the value for a variable using KEY=value format"""
    key, val = key_val.split("=", 1)
    ssm = boto3.client("ssm")
    if app.chamber_compatible_config:
        key_store = key.lower()
        key_display = key.upper()
    else:
        key_store = key_display = key
    name = "/".join([app.parameter_prefix, key_store])
    with halo_success(text=f"setting parameter {key_display}"):
        ssm.put_parameter(Name=name, Value=val, Type="SecureString", Overwrite=True)


@config.command()
@click.argument("key")
def unset(key: str) -> None:
    """Unset (delete) a variable"""
    ssm = boto3.client("ssm")
    if app.chamber_compatible_config:
        key_store = key.lower()
        key_display = key.upper()
    else:
        key_store = key_display = key
    name = "/".join([app.parameter_prefix, key_store])
    with halo_success(text=f"deleting parameter {key_display}"):
        ssm.delete_parameter(Name=name)
