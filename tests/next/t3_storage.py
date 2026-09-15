# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import json

from genlayer import *


class T3Storage(gl.Contract):
    items: TreeMap[str, str]
    log: DynArray[str]
    count: u256

    def __init__(self):
        pass

    @gl.public.write
    def add_item(self, key: str, value: str):
        self.items[key] = value
        self.log.append(json.dumps({"key": key}))
        self.count = u256(int(self.count) + 1)

    @gl.public.view
    def get_item(self, key: str) -> str:
        return self.items[key]
