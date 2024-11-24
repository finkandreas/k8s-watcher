from abc import ABC, abstractmethod
import re

from typing import List, TypedDict

class NotifyMessage(TypedDict):
    summary: str
    body: str

class WatcherBase(ABC):
    @abstractmethod
    def get_notifications(self) -> List[NotifyMessage]:
        raise NotImplemented

def should_exclude(pod_name: str, exclude_list: List[re.Pattern[str]]) -> bool:
    for r in exclude_list:
        if r.fullmatch(pod_name): return True
    return False

