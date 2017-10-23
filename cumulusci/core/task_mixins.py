""" Task Mixins add additional useful behavior to BareTask """

import time

class PollRetry(object):
    """
    PollRetry can be mixed into a BareTask subclass to include polling retry behavior
    """

    def __init__(self, *args, **kwargs):
        self.poll_count = 0
        self.poll_interval_level = 0
        self.poll_interval_s = 1
        self.poll_complete = False
        super(PollRetry, self).__init__(*args, **kwargs)

    def _poll_action(self):
        '''
        Poll something and process the response.
        Set `self.poll_complete = True` to break polling loop.
        '''
        raise NotImplementedError(
            'Subclasses should provide their own implementation'
        )

    def _poll(self):
        ''' poll for a result in a loop '''
        while True:
            self.poll_count += 1
            self._poll_action()
            if self.poll_complete:
                break
            time.sleep(self.poll_interval_s)
            self._poll_update_interval()

    def _poll_update_interval(self):
        ''' update the polling interval to be used next iteration '''
        # Increase by 1 second every 3 polls
        if self.poll_count / 3 > self.poll_interval_level:
            self.poll_interval_level += 1
            self.poll_interval_s += 1
            # No guarantee a user of this mixin has a logger
            # TODO: work on if this is the best way to handler logger in mixin.
            try:
                self.logger.info(
                    'Increased polling interval to %d seconds',
                    self.poll_interval_s,
                )
            except AttributeError:
                pass

class RetryableTask(object):
    def _retry(self):
        while True:
            try:
                self._try()
                break
            except Exception as e:
                if not (self.options['retries'] and self._is_retry_valid(e)):
                    raise
                if self.options['retry_interval']:
                    self.logger.warning(
                        'Sleeping for {} seconds before retry...'.format(
                            self.options['retry_interval']
                        )
                    )
                    time.sleep(self.options['retry_interval'])
                    if self.options['retry_interval_add']:
                        self.options['retry_interval'] += (
                            self.options['retry_interval_add']
                        )
                self.options['retries'] -= 1
                self.logger.warning(
                    'Retrying ({} attempts remaining)'.format(
                        self.options['retries']
                    )
                )

    def _try(self):
        raise NotImplementedError(
            'Subclasses should provide their own implementation'
        )

    def _is_retry_valid(self, e):
        return True
