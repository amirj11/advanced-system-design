import click
from click.exceptions import UsageError
from .client import upload_sample
import sys

USAGE_ERROR = "Usage Error: python -m cortex.client -h/--host <SERVER_HOST> -p/--port <PORT_NUMBER> <PATH_TO_FILE>"


def _show_usage_error(self):
    print(USAGE_ERROR)


UsageError.show = _show_usage_error


@click.command()
@click.argument('action', required=True)
@click.option('-h', '--host', required=True)
@click.option('-p', '--port', required=True)
@click.argument('path')
def parser(action, host, port, path):
    if action == "upload-sample":
        upload_sample(host, int(port), path)
    else:
        print(USAGE_ERROR)
        sys.exit(1)


if __name__ == '__main__':
    parser()
