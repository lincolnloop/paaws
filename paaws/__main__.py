import click
import logging
import os

from .app import app
from .cli import auth, builds, config, deployments, db, logs, ps, shell, create, upgrade


@click.group()
@click.option("app_name", "--app", "-a", help="Name of application")
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
main.add_command(create.create)
main.add_command(upgrade.upgrade)
main.add_command(auth.login)
main.add_command(auth.whoami)

if __name__ == "__main__":
    if "PAAWS_DEBUG" in os.environ:
        logging.basicConfig()
        logging.getLogger("paaws").setLevel(logging.DEBUG)
    main()
