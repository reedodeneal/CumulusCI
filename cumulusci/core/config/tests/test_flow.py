import unittest
from cumulusci.core.config import FlowConfig


class TestFlowConfig(unittest.TestCase):

    def test_init(self):
        config = FlowConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')
