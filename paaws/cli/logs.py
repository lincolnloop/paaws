import urllib.parse
import webbrowser

import boto3
import click
from awslogs.bin import main as awslogs_main
from halo import Halo

from ..app import app


@click.group()
def logs():
    """View application logs"""
    pass


@logs.command()
@click.option(
    "--prefix", default="", help="log stream prefix (use to filter by service or task)"
)
@click.option(
    "--tail", "-t", is_flag=True, default=False, help="continually stream logs"
)
@click.option("--start", "-s", default="5m", help="Start time")
def view(prefix, tail, start):
    """Show application logs"""
    args = [
        "awslogs",
        "get",
        app.log_group,
        f"{prefix}.*",
        "--no-stream",
        "--start",
        start,
    ]
    if tail:
        args.append("--watch")
    with Halo(text="fetching logs", spinner="dots"):
        awslogs_main(args)


@logs.command()
def console():
    """Open logs in web console"""
    # Convert to Amazon's weird URL formatting
    query = urllib.parse.quote(
        "fields @timestamp, @message\n| sort @timestamp desc\n| limit 20"
    ).replace("%", "*")
    log_group = urllib.parse.quote(app.log_group).replace("%", "*")
    region = boto3.session.Session().region_name
    webbrowser.open(
        f"https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:logs-insights$3FqueryDetail$3D~(editorString~'{query}~source~(~'{log_group}))"
    )
