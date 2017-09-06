import datetime
import json
import os
import re

import sarge
from simple_salesforce import Salesforce
import requests

from cumulusci.core.config.base import BaseConfig
from cumulusci.core.exceptions import ScratchOrgException
from cumulusci.oauth.salesforce import SalesforceOAuth2

class OrgConfig(BaseConfig):
    """ Salesforce org configuration (i.e. org credentials) """

    def refresh_oauth_token(self, connected_app):
        client_id = self.client_id
        client_secret = self.client_secret
        if not client_id:
            client_id = connected_app.client_id
            client_secret = connected_app.client_secret
        sf_oauth = SalesforceOAuth2(
            client_id,
            client_secret,
            connected_app.callback_url,  # Callback url isn't really used for this call
            auth_site=self.instance_url,
        )
        resp = sf_oauth.refresh_token(self.refresh_token).json()
        if resp != self.config:
            self.config.update(resp)
        self._load_userinfo()

    @property
    def start_url(self):
        start_url = '%s/secur/frontdoor.jsp?sid=%s' % (
            self.instance_url, self.access_token)
        return start_url

    @property
    def user_id(self):
        return self.id.split('/')[-1]

    @property
    def org_id(self):
        return self.id.split('/')[-2]

    @property
    def username(self):
        """ Username for the org connection. """
        username = self.config.get('username')
        if not username:
            username = self.userinfo__preferred_username
        return username

    def load_userinfo(self):
        self._load_userinfo()

    def _load_userinfo(self):
        headers = {"Authorization": "Bearer " + self.access_token}
        response = requests.get(
            self.instance_url + "/services/oauth2/userinfo", headers=headers)
        if response != self.config.get('userinfo', {}):
            self.config.update({'userinfo': response.json()})


class ScratchOrgConfig(OrgConfig):
    """ Salesforce DX Scratch org configuration """

    @property
    def scratch_info(self):
        if hasattr(self, '_scratch_info'):
            return self._scratch_info

        # Create the org if it hasn't already been created
        if not self.created:
            self.create_org()

        self.logger.info('Getting scratch org info from Salesforce DX')

        # Call force:org:display and parse output to get instance_url and
        # access_token
        command = 'sfdx force:org:display -u {} --json'.format(self.username)
        p = sarge.Command(
            command,
            stderr=sarge.Capture(buffer_size=-1),
            stdout=sarge.Capture(buffer_size=-1),
        )
        p.run()

        org_info = None
        stderr_list = [line.strip() for line in p.stderr]
        stdout_list = [line.strip() for line in p.stdout]

        if p.returncode:
            self.logger.error('Return code: {}'.format(p.returncode))
            for line in stderr_list:
                self.logger.error(line)
            for line in stdout_list:
                self.logger.error(line)
            message = '\nstderr:\n{}'.format('\n'.join(stderr_list))
            message += '\nstdout:\n{}'.format('\n'.join(stdout_list))
            raise ScratchOrgException(message)

        else:
            json_txt = ''.join(stdout_list)

            try:
                org_info = json.loads(''.join(stdout_list))
            except Exception as e:
                raise ScratchOrgException(
                    'Failed to parse json from output. This can happen if '
                    'your scratch org gets deleted.\n  '
                    'Exception: {}\n  Output: {}'.format(
                        e.__class__.__name__,
                        ''.join(stdout_list),
                    )
                )
            org_id = org_info['result']['accessToken'].split('!')[0]

        if org_info['result'].get('password', None) is None:
            self.generate_password()
            return self.scratch_info

        self._scratch_info = {
            'instance_url': org_info['result']['instanceUrl'],
            'access_token': org_info['result']['accessToken'],
            'org_id': org_id,
            'username': org_info['result']['username'],
            'password': org_info['result'].get('password', None),
        }

        self.config.update(self._scratch_info)

        self._scratch_info_date = datetime.datetime.utcnow()

        return self._scratch_info

    @property
    def access_token(self):
        return self.scratch_info['access_token']

    @property
    def instance_url(self):
        return self.scratch_info['instance_url']

    @property
    def org_id(self):
        org_id = self.config.get('org_id')
        if not org_id:
            org_id = self.scratch_info['org_id']
        return org_id

    @property
    def user_id(self):
        if not self.config.get('user_id'):
            sf = Salesforce(
                instance=self.instance_url.replace('https://', ''),
                session_id=self.access_token,
                version='38.0',
            )
            result = sf.query_all(
                "SELECT Id FROM User WHERE UserName='{}'".format(
                    self.username
                )
            )
            self.config['user_id'] = result['records'][0]['Id']
        return self.config['user_id']

    @property
    def username(self):
        username = self.config.get('username')
        if not username:
            username = self.scratch_info['username']
        return username

    @property
    def password(self):
        password = self.config.get('password')
        if not password:
            password = self.scratch_info['password']
        return password

    def create_org(self):
        """ Uses sfdx force:org:create to create the org """
        if not self.config_file:
            # FIXME: raise exception
            return
        if not self.scratch_org_type:
            self.config['scratch_org_type'] = 'workspace'

        devhub = ''
        if self.devhub:
            devhub = ' --targetdevhubusername {}'.format(self.devhub)

        # This feels a little dirty, but the use cases for extra args would mostly
        # work best with env vars
        extraargs = os.environ.get('SFDX_ORG_CREATE_ARGS', '')
        command = 'sfdx force:org:create -f {}{} {}'.format(
            self.config_file, devhub, extraargs)
        self.logger.info(
            'Creating scratch org with command {}'.format(command))
        p = sarge.Command(command, stdout=sarge.Capture(buffer_size=-1))
        p.run()

        org_info = None
        re_obj = re.compile(
            'Successfully created scratch org: (.+), username: (.+)')
        stdout = []
        for line in p.stdout:
            match = re_obj.search(line)
            if match:
                self.config['org_id'] = match.group(1)
                self.config['username'] = match.group(2)
            stdout.append(line)
            self.logger.info(line)

        if p.returncode:
            message = 'Failed to create scratch org: \n{}'.format(
                ''.join(stdout))
            raise ScratchOrgException(message)

        self.generate_password()

        # Flag that this org has been created
        self.config['created'] = True

    def generate_password(self):
        """Generates an org password with the sfdx utility. """

        if self.password_failed:
            self.logger.warn(
                'Skipping resetting password since last attempt failed')
            return

        # Set a random password so it's available via cci org info
        command = 'sfdx force:user:password:generate -u {}'.format(
            self.username)
        self.logger.info(
            'Generating scratch org user password with command {}'.format(command))
        p = sarge.Command(command, stdout=sarge.Capture(
            buffer_size=-1), stderr=sarge.Capture(buffer_size=-1))
        p.run()

        stdout = []
        for line in p.stdout:
            stdout.append(line)
        stderr = []
        for line in p.stderr:
            stderr.append(line)

        if p.returncode:
            self.config['password_failed'] = True
            # Don't throw an exception because of failure creating the
            # password, just notify in a log message
            self.logger.warn(
                'Failed to set password: \n{}\n{}'.format(
                    '\n'.join(stdout), '\n'.join(stderr))
            )

    def delete_org(self):
        """ Uses sfdx force:org:delete to create the org """
        if not self.created:
            self.logger.info(
                'Skipping org deletion: the scratch org has not been created')
            return

        command = 'sfdx force:org:delete -p -u {}'.format(self.username)
        self.logger.info(
            'Deleting scratch org with command {}'.format(command))
        p = sarge.Command(command, stdout=sarge.Capture(buffer_size=-1))
        p.run()

        org_info = None
        stdout = []
        for line in p.stdout:
            stdout.append(line)
            if line.startswith('An error occurred deleting this org'):
                self.logger.error(line)
            else:
                self.logger.info(line)

        if p.returncode:
            message = 'Failed to delete scratch org: \n{}'.format(
                ''.join(stdout))
            raise ScratchOrgException(message)

        # Flag that this org has been created
        self.config['created'] = False
        self.config['username'] = None

    def force_refresh_oauth_token(self):
        # Call force:org:display and parse output to get instance_url and
        # access_token
        command = 'sfdx force:org:open -r -u {}'.format(self.username)
        self.logger.info(
            'Refreshing OAuth token with command: {}'.format(command))
        p = sarge.Command(command, stdout=sarge.Capture(buffer_size=-1))
        p.run()

        stdout_list = []
        for line in p.stdout:
            stdout_list.append(line.strip())

        if p.returncode:
            self.logger.error('Return code: {}'.format(p.returncode))
            for line in stdout_list:
                self.logger.error(line)
            message = 'Message: {}'.format('\n'.join(stdout_list))
            raise ScratchOrgException(message)

    def refresh_oauth_token(self, connected_app):
        """ Use sfdx force:org:describe to refresh token instead of built in OAuth handling """
        if hasattr(self, '_scratch_info'):
            # Cache the scratch_info for 1 hour to avoid unnecessary calls out
            # to sfdx CLI
            delta = datetime.datetime.utcnow() - self._scratch_info_date
            if delta.total_seconds() > 3600:
                del self._scratch_info

            # Force a token refresh
            self.force_refresh_oauth_token()

        # Get org info via sfdx force:org:display
        self.scratch_info
