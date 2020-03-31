import click
from click.exceptions import UsageError
from .saver import Saver, run_saver_wrapper
import sys

USAGE_ERROR = "Usage Error: \n python -m cortex.saver save -d/--database <DB_URL> <topic_name> <data> " \
              "\n python -m cortex.saver run-saver <DB_URL> <MESSAGE_QUEUE_URL>"


def _show_usage_error(self, file=None):
    print(USAGE_ERROR)
    sys.exit(1)


UsageError.show = _show_usage_error


@click.command()
@click.argument('action', required=True)
@click.option('-d', '--database', required=True)
@click.argument('topic', required=True)
@click.argument('data', required=True)
def save(action, database, topic, data):
    saver_ = Saver(database)
    saver_.save(topic, data)


@click.command()
@click.argument('action', required=True)
@click.argument('sql_url', required=True)
@click.argument('message_queue_url', required=True)
def run_saver(action, sql_url, message_queue_url):
    run_saver_wrapper(sql_url, message_queue_url)


if __name__ == '__main__':
    if len(sys.argv) > 2:
        if sys.argv[1] == "run-saver":
            run_saver()
        elif sys.argv[1] == "save":
            save()

        else:
            print(USAGE_ERROR)
            sys.exit(1)
    else:
        print(USAGE_ERROR)
        sys.exit(1)




