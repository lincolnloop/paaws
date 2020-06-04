import click
from halo import Halo
from termcolor import cprint, colored

from ..app import app
from ..formatting import print_header
from ..lib.pipelines import (
    pipeline_list,
    pipeline_detail,
    pipeline_for_app,
    validate_promotion,
    promote,
)


@click.group()
def pipelines():
    """Application pipelines"""
    pass


@pipelines.command("list")
def list_():
    with Halo(text="fetching pipelines", spinner="dots"):
        pipelines = pipeline_list()
    print_header("My Pipelines")
    for name in pipelines.keys():
        print(name)


@pipelines.command()
@click.argument("name")
def info(name):
    pipeline = pipeline_detail(name)
    print_header(name)
    print("")
    cell_width = max([len(k["app"]) for k in pipeline] + ["app name"]) + 1
    cprint(
        "{0: <{width}} stage".format("app name", width=cell_width),
        "white",
        attrs=["bold"],
    )
    for stage in pipeline:
        print(
            colored("{0: <{width}}".format(stage["app"], width=cell_width), "green"),
            stage["stage"],
        )


@pipelines.command("promote")
@click.option("--to", "-t", help="app to promote to", required=True)
def promote_cli(to):
    current = app.current_status()
    promote(
        source_name=app.name,
        source_build_number=current["build_number"],
        source_commit=current["commit"],
        source_build_id=current["build_id"],
        dest=to,
    )
