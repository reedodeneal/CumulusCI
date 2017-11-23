""" Mixins for handling task options """

from cumulusci.core.exceptions import TaskOptionsError

class MarshmallowOptionHandlerMixin(object):
    def _init_options(self, kwargs):
        """ Initializes self.options """
        self.options = self.task_config.options
        if self.options is None:
            self.options = {}
        if kwargs:
            self.options.update(kwargs)
        
        schema = self.get_task_options()()
        self.options, self.errors['options'] = schema.load(self.options)
        

    def _validate_options(self):
        if self.errors['options']:
            raise TaskOptionsError(
                self.errors['options']
            )

class CCIOptionHandlerMixin(object):
    def _init_options(self, kwargs):
        """ Initializes self.options """
        self.options = self.task_config.options
        if self.options is None:
            self.options = {}
        if kwargs:
            self.options.update(kwargs)

        # Handle dynamic lookup of project_config values via $project_config.attr
        for option, value in list(self.options.items()):
            try:
                if value.startswith('$project_config.'):
                    attr = value.replace('$project_config.', '', 1)
                    self.options[option] = getattr(
                        self.project_config, attr, None)
            except AttributeError:
                pass
    
    def _validate_options(self):
        missing_required = []
        for name, config in list(self.get_task_options().items()):
            if config.get('required') is True and name not in self.options:
                missing_required.append(name)

        if missing_required:
            raise TaskOptionsError(
                '{} requires the options ({}) '
                'and no values were provided'.format(
                    self.__class__.__name__,
                    ', '.join(missing_required),
                )
            )
