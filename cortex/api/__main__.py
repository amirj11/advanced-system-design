import click
from click.exceptions import UsageError
from .api import run_api_server


def _show_usage_error(self, file=None):
    print("Usage Error:")
    print("python -m cortex.api run-server -h/--host <host> -p/--port <port> -d/--database <database_url>")


UsageError.show = _show_usage_error


@click.command()
@click.argument('action')
@click.option('-h', '--host', required=True)
@click.option('-p', '--port', required=True)
@click.option('-d', '--database', required=True)
def run_server(action, host, port, database):
    if action == "run-server":
        run_api_server(host, port, database)

    else:
        return _show_usage_error()


if __name__ == '__main__':
    run_server()
