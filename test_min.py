# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class MinTest(gl.Contract):
    count: u256
    name: str

    def __init__(self):
        self.count = u256(0)
        self.name = ""

    @gl.public.write
    def set_name(self, value: str):
        self.name = value
        self.count = u256(int(self.count) + 1)

    @gl.public.view
    def get_name(self) -> str:
        return self.name

    @gl.public.view
    def get_count(self) -> str:
        return "count=" + str(int(self.count))
