# { "Depends": "py-genlayer:latest" }
from genlayer import *


class T0Latest(gl.Contract):
    def __init__(self):
        pass

    @gl.public.view
    def hello(self) -> str:
        return "proofcourt ok"
