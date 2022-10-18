#!/usr/bin/env python

"""
Generates a command stub with predefined input and output strings, useful for testing.

To generate a file called some_command:

command_stub.generate('path/to/some_command', {'a': 'A', '-b --c -d=e': 'F'})

To run the generated stub:

$ path/to/some_command a
A
$ path/to/some_command -b --c -d=e
F

Any other invocation of some_command will print an error. Commands are written to 
path/to/some_command.log.

"""

import json
import os
import sys
from typing import Dict, List, Tuple


def normalize_cmdline(args: List[str]) -> Tuple[str]:
    # could do something better here, to normalize flag order
    return tuple(arg for arg in args)


class CommandHandler:
    def __init__(self, filepath: str):
        self.commands = {}
        self.filepath = filepath
        self.log_filepath = filepath + ".log"
        self.cmdname = os.path.basename(filepath)

    def log(self, *msgs):
        with open(self.log_filepath, "a") as log:
            log.write(" ".join(msgs))
            log.write("\n")
            log.flush()

    def add_command(self, args: List[str], output: str):
        self.commands[normalize_cmdline(args)] = output

    def feed(self, args: List[str]) -> str:
        norm_cmdline = normalize_cmdline(args)
        cmdline = f'{self.cmdname} {" ".join(norm_cmdline)}'
        if norm_cmdline not in self.commands:
            self.log("ERROR:", cmdline)
            raise ValueError(f"Invalid command {cmdline!r}")

        self.log(cmdline)
        return self.commands[norm_cmdline]


commands = {}  # REPLACEMENT_MARKER
marker = "REPLACEMENT_" + "MARKER"


def _replace_line(line, commands_map):
    if marker in line:
        # assumme commands_map is just a Dict[str, str], so rendering repr() should work
        return "commands = " + repr(commands_map)
    else:
        return line


def generate(out_filepath, commands_map: Dict[str, str]):
    source = open(__file__).read()
    if marker not in source:
        raise ValueError(
            "generate() called on a generated file, should be called on command_stub"
        )
    generated = "\n".join(
        _replace_line(line, commands_map) for line in source.splitlines()
    )
    with open(out_filepath, "w") as out:
        out.write(generated)
    os.chmod(out_filepath, 0o775)
    print("Wrote", out_filepath)


if __name__ == "__main__":
    cmd_handler = CommandHandler(sys.argv[0])
    for cmd, output in commands.items():
        if isinstance(cmd, str):
            args = [arg for arg in cmd.split() if arg]
        else:
            args = cmd
        cmd_handler.add_command(args, output)

    print(cmd_handler.feed(sys.argv[1:]))
