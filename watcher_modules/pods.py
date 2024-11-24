import re

from typing import Any, Dict, List

from kubernetes import client

from .common import should_exclude, NotifyMessage, WatcherBase

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
                    if c_new.ready != True and not (c_new.state.terminated and c_new.state.terminated.exit_code == 0):
                        summary = f"🟡 Warning: container {c_new.name} in pod {podName} is not ready (namespace={self._ns})"
                        body= f"{c_new.to_str()}"
                        ret.append(NotifyMessage(summary=summary, body=body))
                        print(f'{c_new=} {c_old=}')
                    if c_new.restart_count > c_old.restart_count:
                        summary = f'🟡 Warning: container {c_new.name} in pod {podName} was restarted (namespace={self._ns})'
                        body = f'Old restart count={c_old.restart_count}, new restart count={c_new.restart_count}'
                        ret.append(NotifyMessage(summary=summary, body=body))
                        print(f'{c_new=} {c_old=}')

        return ret
