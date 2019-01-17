# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import contextlib
import os
import shutil
import sys
import yaml
import codecs
import tempfile
import zipfile

import sgtk
import sgtk.platform.framework
from sgtk.util.filesystem import (
    backup_folder,
    ensure_folder_exists,
    move_folder,
)

logger = sgtk.LogManager.get_logger(__name__)


def bootstrap(engine_name, context, app_path, app_args, **kwargs):
    """
    Interface for older versions of tk-multi-launchapp.

    This is deprecated and now replaced with the ``startup.py`` file
    and ``SoftwareLauncher`` interface.

    Prepares the environment for a tk-aftereffectscc bootstrap. This method
    is called directly from the tk-multi-launchapp.

    :param str engine_name: The name of the engine being used -- "tk-aftereffectscc"
    :param context: The context to use when bootstrapping.
    :param str app_path: The path to the host application being launched.
    :param str app_args: The arguments to be passed to the host application
                         on launch.

    :returns: The host application path and arguments.
    """
    # get the necessary environment variable for launch
    env = compute_environment()
    # set the environment
    os.environ.update(env)


    # all good to go
    return (app_path, app_args)


def _get_adobe_framework_location(tank, descriptor):
    """ This helper method will query the current environment for the configured
        location on disk where the tk-adobe-framework is to be found.

        This is necessary, as the the framework relies on an environment variable
        to be set by the parent engine.

        Args:
        tank (tank.api.Tank): the current sgtk connection
        descriptor (tank.descriptor.descriptor_bundle.EngineDescriptor): 

        Returns (str): The folder path to the latest framework. Empty string if no match.
    """
    environment = tank.pipeline_configuration.get_environment('project')
    required_frameworks = ['{name}_{version}'.format(**v) for v in descriptor.required_frameworks]

    # the following will retrieve position (file and keys) in the current config
    # where the tk-framework-adobe is configured
    framework_location_description = None
    for each_framework in environment.get_frameworks():
        if each_framework.startswith('tk-framework-adobe') and required_frameworks.count(each_framework):
            framework_location_description = environment.find_location_for_framework(each_framework)
            break
    else:
        return ''

    # this will get the framework configuration from the config file
    f = codecs.open(framework_location_description[1], 'r')
    full_config = yaml.load(f.read())
    f.close()
    while framework_location_description[0]:
        full_config = full_config.get(framework_location_description[0].pop(0), {})

    return tank.pipeline_configuration.get_framework_descriptor(full_config.get('location', {})).get_path()
    

def compute_environment(tank, descriptor):
    """
    Return the env vars needed to launch the After Effects plugin.

    This will generate a dictionary of environment variables
    needed in order to launch the After Effects plugin.

    :returns: dictionary of env var string key/value pairs.
    """
    env = {}

    # set the interpreter with which to launch the CC integration
    env["SHOTGUN_ADOBE_PYTHON"] = sys.executable
    env["SHOTGUN_ADOBE_FRAMEWORK_LOCATION"] = _get_adobe_framework_location(tank, descriptor)
    env["SHOTGUN_ENGINE"] = "tk-aftereffectscc"

    # We're going to append all of this Python process's sys.path to the
    # PYTHONPATH environment variable. This will ensure that we have access
    # to all libraries available in this process in subprocesses like the
    # Python process that is spawned by the Shotgun CEP extension on launch
    # of an Adobe host application. We're appending instead of setting because
    # we don't want to stomp on any PYTHONPATH that might already exist that
    # we want to persist when the Python subprocess is spawned.
    sgtk.util.append_path_to_env_var(
        "PYTHONPATH",
        os.pathsep.join(sys.path),
    )
    env["PYTHONPATH"] = os.environ["PYTHONPATH"]

    return env



