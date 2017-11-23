""" Mixins for handling task options """

from cumulusci.core.exceptions import TaskOptionsError

class MarshmallowOptionHandlerMixin(object):
    def _validate_options(self):
        schema = self.get_task_options()()
        result = schema.load(self.options)
        if result.errors:
            raise TaskOptionsError(
                result.errors
            )

class CCIOptionHandlerMixin(object):
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
