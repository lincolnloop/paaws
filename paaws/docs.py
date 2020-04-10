from typing import Union

from click import Command, Group

from .__main__ import main


def list_items(cmd: Union[Command, Group], indent: int) -> list:
    items = []
    for cmd in getattr(cmd, "commands", {}).values():
        items.extend([indent * " " + f"* `{cmd.name}` {cmd.__doc__.strip()}"])
        items.extend(list_items(cmd, indent + 2))
    return items


def generate():
    """Dump docs in Markdown format"""
    for k in sorted(main.commands.keys()):
        print("\n".join([f"### `{k}`", "", main.commands[k].__doc__, ""]))
        sub_commands = list_items(main.commands[k], 0)
        if sub_commands:
            print("\n".join(sub_commands + [""]))


if __name__ == "__main__":
    generate()
