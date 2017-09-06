import logging
import os

import hiyapyco
import raven

from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
from github3 import login

import cumulusci
from cumulusci.core.exceptions import ServiceNotConfigured
from cumulusci.core.exceptions import ServiceNotValid
from cumulusci.core.exceptions import KeychainNotFound


class BaseConfig(object):
    """ Base class for all configuration objects """

    defaults = {}
    search_path = ['config']

    def __init__(self, config=None):
        if config is None:
            self.config = {}
        else:
            self.config = config
        self._init_logger()
        self._load_config()

    def _init_logger(self):
        """ Initializes self.logger """
        self.logger = logging.getLogger(__name__)

    def _load_config(self):
        """ Performs the logic to initialize self.config """
        pass

    def __getattr__(self, name):
        tree = name.split('__')
        if name.startswith('_'):
            raise AttributeError('Attribute {} not found'.format(name))
        value = None
        value_found = False
        for attr in self.search_path:
            config = getattr(self, attr)
            if len(tree) > 1:
                # Walk through the config dictionary using __ as a delimiter
                for key in tree[:-1]:
                    config = config.get(key)
                    if config is None:
                        break
            if config is None:
                continue

            if tree[-1] in config:
                value = config[tree[-1]]
                value_found = True
                break

        if value_found:
            return value
        else:
            return self.defaults.get(name)


class BaseTaskFlowConfig(BaseConfig):
    """ Base class for all configs that contain tasks and flows """

    def list_tasks(self):
        """ Returns a list of task info dictionaries with keys 'name' and 'description' """
        tasks = []
        for task in self.tasks.keys():
            task_info = self.tasks[task]
            if not task_info:
                task_info = {}
            tasks.append({
                'name': task,
                'description': task_info.get('description'),
            })
        return tasks

    def get_task(self, name):
        """ Returns a TaskConfig """
        config = getattr(self, 'tasks__{}'.format(name))
        return TaskConfig(config)

    def list_flows(self):
        """ Returns a list of flow info dictionaries with keys 'name' and 'description' """
        flows = []
        return flows

    def get_flow(self, name):
        """ Returns a FlowConfig """
        config = getattr(self, 'flows__{}'.format(name))
        return FlowConfig(config)


class BaseProjectConfig(BaseTaskFlowConfig):
    """ Base class for a project's configuration which extends the global config """

    search_path = ['config']

    def __init__(self, global_config_obj, config=None):
        self.global_config_obj = global_config_obj
        self.keychain = None
        if not config:
            config = {}
        super(BaseProjectConfig, self).__init__(config=config)

    @property
    def config_global_local(self):
        return self.global_config_obj.config_global_local

    @property
    def config_global(self):
        return self.global_config_obj.config_global

    @property
    def repo_root(self):
        path = os.path.splitdrive(os.getcwd())[1]
        while True:
            if os.path.isdir(os.path.join(path, '.git')):
                return path
            head, tail = os.path.split(path)
            if not tail:
                # reached the root
                break
            path = head

    @property
    def repo_name(self):
        if not self.repo_root:
            return

        in_remote_origin = False
        with open(os.path.join(self.repo_root, '.git', 'config'), 'r') as f:
            for line in f:
                line = line.strip()
                if line == '[remote "origin"]':
                    in_remote_origin = True
                    continue
                if in_remote_origin and line.find('url =') != -1:
                    line_parts = line.split('/')
                    repo_name = line_parts[-1]
                    if repo_name.endswith('.git'):
                        repo_name = repo_name[:-4]
                    return repo_name

    @property
    def repo_url(self):
        if not self.repo_root:
            return
        git_config_file = os.path.join(self.repo_root, '.git', 'config')
        with open(git_config_file, 'r') as f:
            in_remote_origin = False
            for line in f:
                line = line.strip()
                if line == '[remote "origin"]':
                    in_remote_origin = True
                    continue
                if in_remote_origin and 'url = ' in line:
                    return line[7:]

    @property
    def repo_owner(self):
        if not self.repo_root:
            return

        in_remote_origin = False
        with open(os.path.join(self.repo_root, '.git', 'config'), 'r') as f:
            for line in f:
                line = line.strip()
                if line == '[remote "origin"]':
                    in_remote_origin = True
                    continue
                if in_remote_origin and line.find('url =') != -1:
                    line_parts = line.split('/')
                    return line_parts[-2].split(':')[-1]

    @property
    def repo_branch(self):
        if not self.repo_root:
            return

        with open(os.path.join(self.repo_root, '.git', 'HEAD'), 'r') as f:
            branch_ref = f.read().strip()
        if branch_ref.startswith('ref: '):
            return '/'.join(branch_ref[5:].split('/')[2:])

    @property
    def repo_commit(self):
        if not self.repo_root:
            return

        branch = self.repo_branch
        if not branch:
            return

        join_args = [self.repo_root, '.git', 'refs', 'heads']
        join_args.extend(branch.split('/'))
        commit_file = os.path.join(*join_args)

        commit_sha = None
        if os.path.isfile(commit_file):
            with open(commit_file, 'r') as f:
                commit_sha = f.read().strip()
        else:
            packed_refs_path = os.path.join(
                self.repo_root,
                '.git',
                'packed-refs'
            )
            with open(packed_refs_path, 'r') as f:
                for line in f:
                    parts = line.split(' ')
                    if len(parts) == 1:
                        # Skip lines showing the commit sha of a tag on the
                        # preceeding line
                        continue
                    if parts[1].replace('refs/remotes/origin/', '').strip() == branch:
                        commit_sha = parts[0]
                        break

        return commit_sha

    @property
    def use_sentry(self):
        try:
            self.keychain.get_service('sentry')
            return True
        except ServiceNotConfigured:
            return False
        except ServiceNotValid:
            return False

    def init_sentry(self, ):
        """ Initializes sentry.io error logging for this session """
        if not self.use_sentry:
            return

        sentry_config = self.keychain.get_service('sentry')

        tags = {
            'repo': self.repo_name,
            'branch': self.repo_branch,
            'commit': self.repo_commit,
            'cci version': cumulusci.__version__,
        }
        tags.update(self.config.get('sentry_tags', {}))

        env = self.config.get('sentry_environment', 'CumulusCI CLI')

        self.sentry = raven.Client(
            dsn=sentry_config.dsn,
            environment=env,
            tags=tags,
            processors=(
                'raven.processors.SanitizePasswordsProcessor',
            ),
        )

    def get_github_api(self):
        github_config = self.keychain.get_service('github')
        gh = login(github_config.username, github_config.password)
        return gh

    def get_latest_version(self, beta=None):
        """ Query Github Releases to find the latest production or beta release """
        gh = self.get_github_api()
        repo = gh.repository(self.repo_owner, self.repo_name)
        latest_version = None
        for release in repo.iter_releases():
            if beta:
                if 'Beta' not in release.tag_name:
                    continue
            else:
                if 'Beta' in release.tag_name:
                    continue
            version = self.get_version_for_tag(release.tag_name)
            if version is None:
                continue
            version = LooseVersion(version)
            if not latest_version or version > latest_version:
                latest_version = version
        return latest_version

    @property
    def config_project_path(self):
        if not self.repo_root:
            return
        path = os.path.join(self.repo_root, self.config_filename)
        if os.path.isfile(path):
            return path

    @property
    def project_local_dir(self):
        """ location of the user local directory for the project
        e.g., ~/.cumulusci/NPSP-Extension-Test/ """

        # depending on where we are in bootstrapping the YamlGlobalConfig
        # the canonical projectname could be located in one of two places
        if self.project__name:
            name = self.project__name
        else:
            try:
                name = self.config_project['project']['name']
            except KeyError:
                name = ''

        path = os.path.join(
            os.path.expanduser('~'),
            self.global_config_obj.config_local_dir,
            name,
        )
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    def get_tag_for_version(self, version):
        if '(Beta' in version:
            tag_version = version.replace(
                ' (', '-').replace(')', '').replace(' ', '_')
            tag_name = self.project__git__prefix_beta + tag_version
        else:
            tag_name = self.project__git__prefix_release + version
        return tag_name

    def get_version_for_tag(self, tag):
        if not tag.startswith(self.project__git__prefix_beta) and not tag.startswith(self.project__git__prefix_release):
            return None

        if 'Beta' in tag:
            version = tag[len(self.project__git__prefix_beta):]
            version = version.replace('-', ' (').replace('_', ' ') + ')'
        else:
            version = tag[len(self.project__git__prefix_release):]
        return version

    def set_keychain(self, keychain):
        self.keychain = keychain

    def _check_keychain(self):
        if not self.keychain:
            raise KeychainNotFound(
                'Could not find config.keychain. You must call ' +
                'config.set_keychain(keychain) before accessing orgs')

    def list_orgs(self):
        """ Returns a list of all org names for the project """
        self._check_keychain()
        return self.keychain.list_orgs()

    def get_org(self, name):
        """ Returns an OrgConfig for the given org_name """
        self._check_keychain()
        return self.keychain.get_org(name)

    def set_org(self, name, org_config):
        """ Creates or updates an org's oauth info """
        self._check_keychain()
        return self.keychain.set_org(name, org_config)

    def get_static_dependencies(self, dependencies=None):
        """ Resolves the project -> dependencies section of cumulusci.yml
            to convert dynamic github dependencies into static dependencies
            by inspecting the referenced repositories
        """
        if not dependencies:
            dependencies = self.project__dependencies

        if not dependencies:
            return

        static_dependencies = []
        for dependency in dependencies:
            if 'github' not in dependency:
                static_dependencies.append(dependency)
            else:
                static = self.process_github_dependency(dependency)
                static_dependencies.extend(static)
        return static_dependencies

    def pretty_dependencies(self, dependencies, indent=None):
        if not indent:
            indent = 0
        pretty = []
        for dependency in dependencies:
            prefix = '{}  - '.format(" " * indent)
            for key, value in dependency.items():
                extra = []
                if value is None or value is False:
                    continue
                if key == 'dependencies':
                    extra = self.pretty_dependencies(
                        dependency['dependencies'], indent=indent + 4)
                    if not extra:
                        continue
                    value = '\n{}'.format(" " * (indent + 4))

                pretty.append('{}{}: {}'.format(prefix, key, value))
                if extra:
                    pretty.extend(extra)
                prefix = '{}    '.format(" " * indent)
        return pretty

    def process_github_dependency(self, dependency, indent=None):
        if not indent:
            indent = ''

        self.logger.info(
            '{}Processing dependencies from Github repo {}'.format(
                indent,
                dependency['github'],
            )
        )

        skip = dependency.get('skip')
        if not isinstance(skip, list):
            skip = [skip, ]

        # Initialize github3.py API against repo
        gh = self.get_github_api()
        repo_owner, repo_name = dependency['github'].split('/')[3:5]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        repo = gh.repository(repo_owner, repo_name)

        # Get the cumulusci.yml file
        contents = repo.contents('cumulusci.yml')
        cumulusci_yml = hiyapyco.load(contents.decoded)

        # Get the namespace from the cumulusci.yml if set
        namespace = cumulusci_yml.get('project', {}).get(
            'package', {}).get('namespace')

        # Check for unmanaged flag on a namespaced package
        unmanaged = namespace and dependency.get('unmanaged') is True

        # Look for subfolders under unpackaged/pre
        unpackaged_pre = []
        contents = repo.contents('unpackaged/pre')
        if contents:
            for dirname in contents.keys():
                if 'unpackaged/pre/{}'.format(dirname) in skip:
                    continue
                subfolder = "{}-{}/unpackaged/pre/{}".format(
                    repo.name, repo.default_branch, dirname)
                zip_url = "{}/archive/{}.zip".format(
                    repo.html_url, repo.default_branch)

                unpackaged_pre.append({
                    'zip_url': zip_url,
                    'subfolder': subfolder,
                    'unmanaged': dependency.get('unmanaged'),
                    'namespace_tokenize': dependency.get('namespace_tokenize'),
                    'namespace_inject': dependency.get('namespace_inject'),
                    'namespace_strip': dependency.get('namespace_strip'),
                })

        # Look for metadata under src (deployed if no namespace)
        unmanaged_src = None
        if unmanaged or not namespace:
            contents = repo.contents('src')
            if contents:
                zip_url = "{}/archive/{}.zip".format(
                    repo.html_url, repo.default_branch)
                subfolder = "{}-{}/src".format(repo.name, repo.default_branch)

                unmanaged_src = {
                    'zip_url': zip_url,
                    'subfolder': subfolder,
                    'unmanaged': dependency.get('unmanaged'),
                    'namespace_tokenize': dependency.get('namespace_tokenize'),
                    'namespace_inject': dependency.get('namespace_inject'),
                    'namespace_strip': dependency.get('namespace_strip'),
                }

        # Look for subfolders under unpackaged/post
        unpackaged_post = []
        contents = repo.contents('unpackaged/post')
        if contents:
            for dirname in contents.keys():
                if 'unpackaged/post/{}'.format(dirname) in skip:
                    continue
                zip_url = "{}/archive/{}.zip".format(
                    repo.html_url, repo.default_branch)
                subfolder = "{}-{}/unpackaged/post/{}".format(
                    repo.name, repo.default_branch, dirname)

                dependency = {
                    'zip_url': zip_url,
                    'subfolder': subfolder,
                    'unmanaged': dependency.get('unmanaged'),
                    'namespace_tokenize': dependency.get('namespace_tokenize'),
                    'namespace_inject': dependency.get('namespace_inject'),
                    'namespace_strip': dependency.get('namespace_strip'),
                }
                # By default, we always inject the project's namespace into
                # unpackaged/post metadata
                if namespace and not dependency.get('namespace_inject'):
                    dependency['namespace_inject'] = namespace
                    dependency['unmananged'] = unmanaged
                unpackaged_post.append(dependency)

        project = cumulusci_yml.get('project', {})
        dependencies = project.get('dependencies')
        if dependencies:
            dependencies = self.get_static_dependencies(dependencies)
        version = None

        if namespace and not unmanaged:
            # Get version
            version = dependency.get('version')
            if 'version' not in dependency or dependency['version'] == 'latest':
                # github3.py doesn't support the latest release API so we hack
                # it together here
                url = repo._build_url('releases/latest', base_url=repo._api)
                try:
                    version = repo._get(url).json()['name']
                except Exception as e:
                    self.logger.warn('{}{}: {}'.format(
                        indent, e.__class__.__name__, e.message))

            if not version:
                self.logger.warn(
                    '{}Could not find latest release for {}'.format(indent, namespace))

        # Create the final ordered list of all parsed dependencies
        repo_dependencies = []

        # unpackaged/pre/*
        if unpackaged_pre:
            repo_dependencies.extend(unpackaged_pre)

        # Latest managed release (if referenced repo has a namespace)
        if namespace and not unmanaged:
            if version:
                # If a latest prod version was found, make the dependencies a
                # child of that install
                dependency = {
                    'namespace': namespace,
                    'version': version,
                }
                if dependencies:
                    dependency['dependencies'] = dependencies

                repo_dependencies.append(dependency)
            elif dependencies:
                repo_dependencies.extend(dependencies)

        # Unmanaged metadata from src (if referenced repo doesn't have a
        # namespace)
        else:
            if dependencies:
                repo_dependencies.extend(dependencies)
            if unmanaged_src:
                repo_dependencies.append(unmanaged_src)

        # unpackaged/post/*
        if unpackaged_post:
            repo_dependencies.extend(unpackaged_post)

        return repo_dependencies


class BaseGlobalConfig(BaseTaskFlowConfig):
    """ Base class for the global config which contains all configuration not specific to projects """
    project_config_class = BaseProjectConfig

    config_local_dir = '.cumulusci'

    def list_projects(self):
        """ Returns a list of project names """
        raise NotImplementedError('Subclasses must provide an implementation')

    def get_project_config(self):
        """ Returns a ProjectConfig for the given project """
        return self.project_config_class(self)

    def create_project(self, project_name, config):
        """ Creates a new project configuration and returns it """
        raise NotImplementedError('Subclasses must provide an implementation')
