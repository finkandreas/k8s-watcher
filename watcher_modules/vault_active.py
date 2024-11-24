import re

from typing import Any, Dict, List, Optional

from kubernetes import client

from .common import should_exclude, NotifyMessage, WatcherBase

def vault_pod_marked_active(labels: Optional[Dict[str, str]]) -> bool:
    if labels is None: return False
    return labels.get('vault-active', '') == 'true'

class VaultActiveWatcher(WatcherBase):
    def __init__(self, namespace: str, client: client.CoreV1Api, exclude_pods: List[re.Pattern[str]]) -> None:
        self._last_active: str = ''
        self._kc = client
        self._ns = namespace
        self._exclude_pods = exclude_pods


    def get_notifications(self) -> List[NotifyMessage]:
        ret = []
        pods = self._kc.list_namespaced_pod(self._ns)
        active_pods = [ x for x in pods.items if vault_pod_marked_active(x.metadata.labels)]
        if len(active_pods) == 0:
            ret.append(NotifyMessage(summary='🔴 Error: No vault pod is marked as active', body='Vault deployment is broken'))
        if len(active_pods) == 1:
            if self._last_active == '':
                # first run - remember the active pod
                self._last_active = active_pods[0].metadata.name
            elif self._last_active != active_pods[0].metadata.name:
                body = f'Old active: {self._last_active}\nNew active: {active_pods[0].metadata.name}\n'
                body += 'Vault was probably down for some short time'
                ret.append(NotifyMessage(summary='🟡 Warning: The active vault pod changed', body=body))
                self._last_active = active_pods[0].metadata.name
        if len(active_pods) > 1:
            body = '\n'.join([f'marked as active: {p.metadata.name}' for p in active_pods])
            ret.append(NotifyMessage(summary='🟡 Warning: More than one pod is marked as active', body=body))
        return ret
