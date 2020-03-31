import click
from click.exceptions import UsageError
from .parsers import run_parser_wrapper
import sys

USAGE_ERROR = "Usage Error:\npython -m cortex.parsers parse '<parser_name>' '<data>' \n" \
              "python -m cortex.parsers run-parser '<parser_name>' '<message_queue_url>'"


def _show_usage_error(self, file=None):
    print(USAGE_ERROR)


UsageError.show = _show_usage_error


@click.command()
@click.argument('action', required=True)
@click.argument('parser_name', required=True)
@click.argument('arg2', required=True)  # can be data to parse or a message_queue URL
def parser(action, parser_name, arg2):
    if action == "parse":
        return run_parser_wrapper(parser_name, data=arg2, action="once")
        # return run_parser(parser_name, data)
    if action == "run-parser":
        # run_parser_service(parser_name, arg2)
        run_parser_wrapper(parser_name, mq=arg2, action="service")

    else:
        print(USAGE_ERROR)
        sys.exit(1)


if __name__ == '__main__':
    parser()
