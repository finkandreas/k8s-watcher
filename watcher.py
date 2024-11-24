import argparse
import os
import re
import time
import traceback

from typing import List

from kubernetes import client, config
import requests

from watcher_modules.common import NotifyMessage, WatcherBase


if __name__ == '__main__':
    if 'NOTIFY_URL' not in os.environ:
        raise Exception("Missing notification url. You must provide it in the environment variable NOTIFY_URL")
    notify_url = os.environ['NOTIFY_URL']

    parser = argparse.ArgumentParser(prog="K8s watcher",
                                     description="Watch kubernetes namespace for events and pod restarts")
    parser.add_argument('--exclude',
                        action='append',
                        help="Exclude pod matching regular expression (use multiple times for multiple excludes)")
    parser.add_argument('modules',
                        nargs='+',
                        help='add module to watcher')
    parsed_args = parser.parse_args()
    exclude_list = [re.compile(x) for x in parsed_args.exclude] if parsed_args.exclude else []
    print(f'Excluding pods {exclude_list}')

    namespace = 'default'
    if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/namespace'):
        namespace = open('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read()
    config.load_config()
    kubeclient = client.CoreV1Api()

    # setup watchers
    watchers: List[WatcherBase] = []
    for m in parsed_args.modules:
        import watcher_modules
        watchers.append(watcher_modules.__dict__[m](namespace, kubeclient, exclude_list))
    print(watchers)
    exit(0)

    while True:
        try:
            new_events = []
            for watcher in watcher:
                new_events += watcher.get_notifications()
            if new_events:
                for ev in new_events:
                    r = requests.post(notify_url, json=ev)
                    if r.status_code >= 400:
                        print(f'Failed sending notification {r.status_code=} {r.text=}. All headers:\n{r.headers=}')
        except Exception as e:
            print("Error: Caught an exception")
            traceback.print_exception(e)

        # flush any output
        print(end='', flush=True)
        time.sleep(60)
