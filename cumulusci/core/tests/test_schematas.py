""" Tests for the CumulusCI task module """
from __future__ import unicode_literals

import unittest

from cumulusci.core.tasks import BaseTask, SchematicTask
from cumulusci.core.config import BaseGlobalConfig
from cumulusci.core.config import BaseProjectConfig
from cumulusci.core.config import TaskConfig
from cumulusci.core.config import OrgConfig
from cumulusci.core.exceptions import TaskOptionsError

from marshmallow import Schema, fields
class DynTestSchema(Schema):
    test_option = fields.Str(required=True, metadata={'description': 'test_option is required, for test reasons.'})

class DynTask(SchematicTask):
    task_options = DynTestSchema
    
    def _run_task(self):
        return -1

class TestBaseTaskCallable(unittest.TestCase):
    task_class = DynTask

    @classmethod
    def setUpClass(cls):
        super(TestBaseTaskCallable, cls).setUpClass()

    def setUp(self):
        self.global_config = BaseGlobalConfig()
        self.project_config = BaseProjectConfig(self.global_config)
        self.org_config = OrgConfig({
            'username': '00D000000000001',
            'org_id': 'sample@example'
        })
        self.task_config = TaskConfig()

    def test_dynamic_options(self):
        """ Option values can lookup values from project_config """
        self.project_config.config['foo'] = {'bar': 'baz'}
        self.task_config.config['options'] = {
            'test_option': '$project_config.foo__bar',
        }
        task = self.__class__.task_class(
            self.project_config,
            self.task_config,
            self.org_config
        )
        self.assertEquals('baz', task.options['test_option'])

    def test_required_options(self):
        """ Task Options marked required fail to validate """

        with self.assertRaises(TaskOptionsError):
            task = self.__class__.task_class(
                self.project_config,
                self.task_config,
                self.org_config
            )
