import unittest
from cumulusci.core.config import OrgConfig
from cumulusci.core.config import ScratchOrgConfig

class TestOrgConfig(unittest.TestCase):

    def test_init(self):
        config = OrgConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')

class TestScratchOrgConfig(unittest.TestCase):

    def test_init(self):
        config = ScratchOrgConfig()
        config.config = {'foo': 'bar'}
        self.assertEquals(config.foo, 'bar')
