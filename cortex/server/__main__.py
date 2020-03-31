import click
from click.exceptions import UsageError
from .server import run_server
import sys

USAGE_ERROR = "Usage Error: python -m cortex.server -h/--host <SERVER_HOST> -p/--port <PORT_NUMBER> <MESSAGE_QUEUE_URL>"


def _show_usage_error(self):
    print(USAGE_ERROR)


UsageError.show = _show_usage_error


@click.command()
@click.argument('action')
@click.option('-h', '--host', default="127.0.0.1")
@click.option('-p', '--port', default=8000)
@click.argument('message_queue', default="rabbitmq://127.0.0.1:5672/")
def parser(action, host, port, message_queue):
    if action == "run-server":
        run_server(host, port, message_queue, publish_method="message_queue")

    else:
        print(USAGE_ERROR)
        sys.exit(1)


if __name__ == '__main__':
    parser()
