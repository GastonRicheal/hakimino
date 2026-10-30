"""Interactive secret prompts; no secrets in command arguments."""
import argparse
import getpass
import json
import sys
import warnings

from .vault import VaultError, generate_password, operate


def secret(prompt):
    # Refuse getpass's echoing fallback if the terminal cannot disable echo.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hakimino local encrypted password vault")
    parser.add_argument("--vault", default="personal.vault", help="Path to a .vault file")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="Create a vault without overwriting an existing one")
    commands.add_parser("list", help="List entry labels only")
    show = commands.add_parser("show", help="Show username; reveal password only on request")
    show.add_argument("label")
    show.add_argument("--reveal", action="store_true")
    add = commands.add_parser("add", help="Add an entry, with a prompted or generated password")
    add.add_argument("label")
    add.add_argument("--generate", action="store_true")
    add.add_argument("--length", type=int, default=24)
    delete = commands.add_parser("delete", help="Delete one entry after confirmation")
    delete.add_argument("label")
    generate = commands.add_parser("generate", help="Print a new password (visible in terminal)")
    generate.add_argument("--length", type=int, default=24)
    args = parser.parse_args(argv)
    try:
        if args.action == "generate":
            print(generate_password(args.length))
            return 0
        master = secret("Master password: ")
        if args.action == "init" and master != secret("Confirm master password: "):
            raise VaultError("Master passwords do not match.")
        kwargs = {"label": getattr(args, "label", None)}
        if args.action == "add":
            kwargs["username"] = input("Entry username: ")
            kwargs["entry_password"] = (generate_password(args.length) if args.generate
                                        else secret("Entry password: "))
        if args.action == "delete" and input("Delete this entry? Type DELETE: ") != "DELETE":
            print("Cancelled.")
            return 0
        result = operate(args.vault, master, args.action, **kwargs)
        if args.action == "show":
            if not args.reveal:
                result = {**result, "password": "[hidden; use --reveal]"}
            print(json.dumps(result, ensure_ascii=True))
        elif args.action == "list":
            print(json.dumps(result, ensure_ascii=True))
        else:
            print("Done.")
        return 0
    except (VaultError, OSError, getpass.GetPassWarning) as exc:
        # File errors do not contain entry data or passwords.
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.", file=sys.stderr)
        return 1
