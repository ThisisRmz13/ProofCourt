# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class T2Payable(gl.Contract):
    total: u256

    def __init__(self):
        pass

    @gl.public.write.payable
    def deposit(self):
        value = gl.message.value
        self.total = u256(int(self.total) + int(value))

    @gl.public.view
    def get_total(self) -> str:
        return "total=" + str(int(self.total))
