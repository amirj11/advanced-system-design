import click
from click.exceptions import UsageError
from .gui import run_server
import json
import requests


def _show_usage_error(self, file=None):
    print_usage()


def print_usage():
    print("Usage Error:")
    print("python -m cortex.gui run-server -h/--host <HOST_IP> -p/--port <PORT> -d/--database <DATABASE_URL>")


UsageError.show = _show_usage_error


@click.command()
@click.argument('action', required=True)
@click.option('-h', '--host', required=True, default="127.0.0.1")
@click.option('-p', '--port', required=True, default="8010")
@click.option('-d', '--database', required=True, default="mongodb://127.0.0.1:27017/")
def run_server_wrapper(action, host, port, database):
    if action == "run-server":
        run_server(host, port, database)
    else:
        print("in else")
        return print_usage()


if __name__ == '__main__':
    run_server_wrapper()
