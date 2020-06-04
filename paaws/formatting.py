from termcolor import colored


def print_header(text: str, color: str = "white") -> None:
    print(
        colored("===", attrs=["dark"]), colored(text, color, attrs=["bold"]),
    )
