import click
from click.exceptions import UsageError
import json
import requests


def _show_usage_error(self, file=None):
    print_usage()


def print_usage():
    print("Usage Error:")
    print("python -m cortex.cli get-users")
    print("python -m cortex.cli get-user <user_id>")
    print("python -m cortex.cli get-snapshots <user_id>")
    print("python -m cortex.cli get-snapshot <user_id> <snapshot_timestamp")
    print("python -m cortex.cli get-result <user_id> <snapshot_timestamp> <result_type>")


UsageError.show = _show_usage_error


@click.command()
@click.argument('action', required=True)
@click.argument('user_id', required=False)
@click.argument('snapshot_id', required=False)
@click.argument('result_name', required=False)
@click.option('-h', '--host', required=False, default="127.0.0.1")
@click.option('-p', '--port', required=False, default="5000")
@click.option('-s', '--save', required=False, default=False)
def run_server(action, user_id, snapshot_id, result_name, host, port, save):
    url = "http://{}:{}".format(host, port)
    if action == "get-users":
        result = requests.get("{}/users".format(url))
    elif action == "get-user":
        if not user_id:
            return print_usage()
        result = requests.get("{}/users/{}".format(url, user_id))
    elif action == "get-snapshots":
        if not user_id:
            return print_usage()
        result = requests.get("{}/users/{}/snapshots".format(url, user_id))
    elif action == "get-snapshot":
        if not user_id or not snapshot_id:
            return print_usage()
        result = requests.get("{}/users/{}/snapshots/{}".format(url, user_id, snapshot_id))
    elif action == "get-result":
        if not user_id or not snapshot_id or not result_name:
            return print_usage()
        result = requests.get("{}/users/{}/snapshots/{}/{}".format(url, user_id, snapshot_id, result_name))
        if save:
            with open(save, "w") as f:
                content = json.loads(result.content)
                for k, v in content.items():
                    f.write("{}: {}\n".format(k, v))
            return
    else:
        return print_usage()

    print("Response from API to query:")
    print("Return code: {}".format(result.status_code))
    data = json.loads(result.content)

    if isinstance(data, dict):
        for k, v in data.items():
            print("{}: {}".format(k, v))

    else:
        for item in data:
            print(item)


if __name__ == '__main__':
    run_server()
