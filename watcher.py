import pprint
import os
import argparse
import re
import sys
import time
import traceback

from typing import Any, Dict, List, TypedDict

from kubernetes import client, config
import requests


class NotifyMessage(TypedDict):
    summary: str
    body: str


def should_exclude(pod_name: str, exclude_list: List[re.Pattern[str]]) -> bool:
    for r in exclude_list:
        if r.fullmatch(pod_name): return True
    return False


class EventWatcher(object):
    def __init__(self, namespace: str, client: client.CoreV1Api, exclude_pods: List[re.Pattern[str]]) -> None:
        self._seen_events: Dict[str, Any] = {}
        self._kc = client
        self._ns = namespace
        self._exclude_pods = exclude_pods
        self._first_run = True

    def get_notifications(self) -> List[NotifyMessage]:
        ret = []
        events = self._kc.list_namespaced_event(self._ns)
        interesting = [x for x in events.items if x.type != 'Normal']
        for ev in interesting:
            if should_exclude(ev.involved_object.name, self._exclude_pods):
                print(f"Not notifying for {ev.involved_object.name} because we matched an exclude pattern")
                continue
            if ev.metadata.uid not in self._seen_events:
                # new event - we do not monitor if the counter of the event is increasing
                summary = f'{ev.type}: New event in {self._ns}'
                body = f'pod: {ev.involved_object.name}\nfield_path: {ev.involved_object.field_path}\nmessage: {ev.message}'
                ret.append(NotifyMessage(summary=summary,body=body))
                self._seen_events[ev.metadata.uid] = True

        if self._first_run:
            self._first_run = False
            return []
        return ret

class PodWatcher(object):
    def __init__(self, namespace: str, client: client.CoreV1Api, exclude_pods: List[re.Pattern[str]]) -> None:
        self._last_pods: Dict[str, Any] = {}
        self._kc = client
        self._ns = namespace
        self._exclude_pods = exclude_pods
        self._first_run = True

    def get_notifications(self) -> List[NotifyMessage]:
        ret = []
        pods = self._kc.list_namespaced_pod(self._ns)
        for p in pods.items:
            if should_exclude(p.metadata.name, self._exclude_pods):
                print(f"Not notifying for {p.metadata.name} because we matched an exclude pattern")
                continue
            if p.metadata.uid not in self._last_pods:
                # new pod - register it now - do not assume that this is some error
                self._last_pods[p.metadata.uid] = p
            else:
                podName = p.metadata.name
                prevPod = self._last_pods[p.metadata.uid]
                self._last_pods[p.metadata.uid] = p
                for c_old, c_new in zip(prevPod.status.container_statuses, p.status.container_statuses):
                    if c_old.name != c_new.name:
                        print(f"Error: The container names do not match. {c_old.name=} {c_new.name}")
                        continue
                    if c_new.ready != True and c_old.ready == True:
                        summary = f"Warning: container {c_new.name} in pod {podName} is not ready"
                        body= f"{c_new.to_str()}"
                        ret.append(NotifyMessage(summary=summary, body=body))
                    if c_new.restart_count > c_old.restart_count:
                        summary = f'Warning: container {c_new.name} in pod {podName} was restarted.'
                        body = f'Old restart count={c_old.restart_count}, new restart count={c_new.restart_count}'
                        ret.append(NotifyMessage(summary=summary, body=body))

        return ret



if __name__ == '__main__':
    if 'NOTIFY_URL' not in os.environ:
        raise Exception("Missing notification url. You must provide it in the environment variable NOTIFY_URL")
    notify_url = os.environ['NOTIFY_URL']

    parser = argparse.ArgumentParser(prog="K8s watcher",
                                     description="Watch kubernetes namespace for events and pod restarts")
    parser.add_argument('--exclude',
                        action='append',
                        help="Exclude pod matching regular expression (use multiple times for multiple excludes)")
    parsed_args = parser.parse_args()
    exclude_list = [re.compile(x) for x in parsed_args.exclude]
    print(f'Excluding pods {exclude_list}')

    namespace = 'default'
    if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/namespace'):
        namespace = open('/var/run/secrets/kubernetes.io/serviceaccount/namespace').read()
    config.load_config()
    kubeclient = client.CoreV1Api()

    # setup watchers
    ev_watch = EventWatcher(namespace, kubeclient, exclude_list)
    pod_watch = PodWatcher(namespace, kubeclient, exclude_list)

    while True:
        try:
            new_events = ev_watch.get_notifications()
            new_events += pod_watch.get_notifications()
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
