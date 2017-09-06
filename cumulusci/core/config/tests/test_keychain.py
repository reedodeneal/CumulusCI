import unittest
from cumulusci.core.config import ConnectedAppOAuthConfig
from cumulusci.core.config import ServiceConfig

class TestConnectedAppOAuthConfig(unittest.TestCase):

    def test_init(self):
        config = ConnectedAppOAuthConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')

class TestServiceConfig(unittest.TestCase):

    def test_init(self):
        config = ServiceConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')
