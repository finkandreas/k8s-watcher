import re

from typing import Any, Dict, List

from kubernetes import client

from .common import should_exclude, NotifyMessage, WatcherBase

class EventWatcher(WatcherBase):
    def __init__(self, namespace: str, client: client.CoreV1Api, exclude_pods: List[re.Pattern[str]] = []) -> None:
        self._seen_events: Dict[str, Any] = {}
        self._kc = client
        self._ns = namespace
        self._exclude_pods = [re.compile(x) for x in exclude_pods]
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
                prefix=''
                if ev.type.lower() == 'warning': prefix='🟡 '
                elif ev.type.lower() == 'error': prefix='🔴 '
                summary = f'{prefix}{ev.type}: New event in namespace={self._ns}'
                body = f'pod: {ev.involved_object.name}\nfield_path: {ev.involved_object.field_path}\nmessage: {ev.message}'
                ret.append(NotifyMessage(summary=summary,body=body))
                self._seen_events[ev.metadata.uid] = True
                print(f'{ev=}')

        if self._first_run:
            self._first_run = False
            return []
        return ret
