import os

import hiyapyco
import yaml

import cumulusci
from cumulusci.core.config.base import BaseProjectConfig
from cumulusci.core.config.base import BaseGlobalConfig
from cumulusci.core.exceptions import NotInProject
from cumulusci.core.exceptions import ProjectConfigNotFound

class YamlProjectConfig(BaseProjectConfig):
    config_filename = 'cumulusci.yml'

    def __init__(self, *args, **kwargs):
        # Initialize the dictionaries for the individual configs
        self.config_project = {}
        self.config_project_local = {}
        self.config_additional_yaml = {}

        # optionally pass in a kwarg named 'additional_yaml' that will
        # be added to the YAML merge stack.
        self.additional_yaml = None
        if kwargs.has_key('additional_yaml'):
            self.additional_yaml = kwargs.pop('additional_yaml')

        super(YamlProjectConfig, self).__init__(*args, **kwargs)

    @property
    def config_project_local_path(self):
        path = os.path.join(
            self.project_local_dir,
            self.config_filename,
        )
        if os.path.isfile(path):
            return path

    def _load_config(self):
        """ Loads the configuration for the project """
        # Verify that we're in a project
        repo_root = self.repo_root
        if not repo_root:
            raise NotInProject(
                'No repository found in current path.  You must be inside a repository to initialize the project configuration')

        # Verify that the project's root has a config file
        if not self.config_project_path:
            raise ProjectConfigNotFound(
                'The file {} was not found in the repo root: {}'.format(
                    self.config_filename,
                    repo_root
                )
            )

        # Start the merged yaml config from the global and global local configs
        merge_yaml = [self.global_config_obj.config_global_path]
        if self.global_config_obj.config_global_local_path:
            merge_yaml.append(self.global_config_obj.config_global_local_path)

        # Load the project's yaml config file
        with open(self.config_project_path, 'r') as f_config:
            project_config = yaml.load(f_config)
        if project_config:
            self.config_project.update(project_config)
            merge_yaml.append(self.config_project_path)

        # Load the local project yaml config file if it exists
        if self.config_project_local_path:
            with open(self.config_project_local_path, 'r') as f_local_config:
                local_config = yaml.load(f_local_config)
            if local_config:
                self.config_project_local.update(local_config)
                merge_yaml.append(self.config_project_local_path)

        # merge in any additional yaml that was passed along
        if self.additional_yaml:
            additional_yaml_config = yaml.load(self.additional_yaml)
            if additional_yaml_config:
                self.config_additional_yaml.update(additional_yaml_config)
                merge_yaml.append(self.additional_yaml)

        self.config = hiyapyco.load(*merge_yaml, method=hiyapyco.METHOD_MERGE)


class YamlGlobalConfig(BaseGlobalConfig):
    config_filename = 'cumulusci.yml'
    config_local_dir = '.cumulusci'
    project_config_class = YamlProjectConfig

    def __init__(self):
        self.config_global_local = {}
        self.config_global = {}
        super(YamlGlobalConfig, self).__init__()

    @property
    def config_global_local_path(self):
        directory = os.path.join(
            os.path.expanduser('~'),
            self.config_local_dir,
        )
        if not os.path.exists(directory):
            os.makedirs(directory)

        config_path = os.path.join(
            directory,
            self.config_filename,
        )
        if not os.path.isfile(config_path):
            return None

        return config_path

    def _load_config(self):
        """ Loads the local configuration """
        # load the global config
        self._load_global_config()

        merge_yaml = [self.config_global_path]

        # Load the local config
        if self.config_global_local_path:
            config = yaml.load(open(self.config_global_local_path, 'r'))
            self.config_global_local = config
            if config:
                merge_yaml.append(self.config_global_local_path)

        self.config = hiyapyco.load(*merge_yaml, method=hiyapyco.METHOD_MERGE)

    @property
    def config_global_path(self):
        return os.path.abspath(os.path.join(
            cumulusci.__location__,
            self.config_filename,
        ))

    def _load_global_config(self):
        """ Loads the configuration for the project """

        # Load the global cumulusci.yml file
        with open(self.config_global_path, 'r') as f_config:
            config = yaml.load(f_config)
        self.config_global = config
