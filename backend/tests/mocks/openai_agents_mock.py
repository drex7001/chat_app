
# This is a fake module to satisfy imports during testing in environment without the real package
import sys
from unittest.mock import MagicMock

class Agent:
    def __init__(self, name, instructions, tools, model):
        self.name = name
        self.instructions = instructions
        self.tools = tools
        self.model = model

class Runner:
    @staticmethod
    async def run(*args, **kwargs):
        pass

# Inject into sys.modules
module = MagicMock()
module.Agent = Agent
module.Runner = Runner
sys.modules["agents"] = module
