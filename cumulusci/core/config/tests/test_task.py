import unittest
from cumulusci.core.config import TaskConfig


class TestTaskConfig(unittest.TestCase):

    def test_init(self):
        config = TaskConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')
