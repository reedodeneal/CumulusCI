""" Mixins for handling task options """

from cumulusci.core.exceptions import TaskOptionsError

from marshmallow import Schema, fields, pre_load


VAR_SYMBOL = '$project_config.'

def process_dynamic_options(context, in_data):
    for option, value in list(in_data.items()):
        if value.startswith(VAR_SYMBOL):
            in_data[option] = getattr(
                context.project_config,
                value.replace(VAR_SYMBOL, '', 1),
                None
            )

    return in_data

class TaskSchema(Schema):
    @pre_load
    def process_project_config(self, in_data):
        return process_dynamic_options(self.context, in_data)

class MarshmallowOptionHandlerMixin(object):
    def _init_options(self, kwargs):
        """ Initializes self.options """
        self.options = self.task_config.options
        if self.options is None:
            self.options = {}
        if kwargs:
            self.options.update(kwargs)
        
        schema = self.get_task_options()(context=self)
        self.options, self.errors['options'] = schema.load(self.options)

class CCIOptionHandlerMixin(object):
    def _init_options(self, kwargs):
        """ Initializes self.options """
        self.options = self.task_config.options
        if self.options is None:
            self.options = {}
        if kwargs:
            self.options.update(kwargs)

        process_dynamic_options(self, self.options)

        self.errors['options'] = {}
        for name, config in list(self.get_task_options().items()):
            if config.get('required') is True and name not in self.options:
                self.errors['options']['name'] = 'No data provided for required option.'

