import argparse
import os
import time
import traceback

from typing import List

import kubernetes
import requests
import yaml

from watcher_modules.common import NotifyMessage, WatcherBase


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="K8s watcher",
                                     description="Watch kubernetes namespace for events, pod restarts or any custom watcher")
    parser.add_argument('--config',
                        help='path to config file')
    parsed_args = parser.parse_args()
    with open(parsed_args.config, 'r') as config_file:
        config = yaml.safe_load(config_file)

    if 'notify_url' not in config:
        raise Exception("Missing notification url. You must provide it in the environment variable NOTIFY_URL")
    notify_url = config['notify_url']

    if not isinstance(config.get('modules', None), list):
        raise Exception('modules missing in config')

    namespace = 'default'
    if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/namespace'):
        namespace = open('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read()
    kubernetesconfig.load_config()
    kubeclient = kubernetes.client.CoreV1Api()

    # setup watchers
    watchers: List[WatcherBase] = []
    import watcher_modules
    for m in config['modules']:
        if 'watcher' not in m:
            raise Exception("module element is missing mandatory `watcher` field")
        watcher_type = m['watcher']
        watcher_options = {k:v for k,v in m.items() if k!='watcher'}
        print(f'Initializing watcher {watcher_type} with the options {watcher_options}')
        watchers.append(watcher_modules.__dict__[watcher_type](namespace, kubeclient, **watcher_options))

    while True:
        try:
            new_events = []
            for watcher in watchers:
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
