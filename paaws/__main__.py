import click

from .app import app
from .cli import builds, config, deployments, db, logs, ps, shell


@click.group()
@click.option("app_name", "--app", "-a", help="Name of application", required=True)
def main(app_name):
    if app_name:
        app.setup(name=app_name)


main.add_command(builds.builds)
main.add_command(shell.shell)
main.add_command(deployments.deployments)
main.add_command(db.db)
main.add_command(config.config)
main.add_command(logs.logs)
main.add_command(ps.ps)

if __name__ == "__main__":
    main()
