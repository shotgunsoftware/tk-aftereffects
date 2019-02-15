# Copyright (c) 2019 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys


import sgtk


logger = sgtk.LogManager.get_logger(__name__)


class EngineConfigurationError(Exception): pass


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


def _get_adobe_framework_location():
    """
    This helper method will query the current environment for the configured
    location on disk where the tk-adobe-framework is to be found.

    This is necessary, as the the framework relies on an environment variable
    to be set by the parent engine.

    Returns (str): The folder path to the latest framework. Empty string if no match.
    """
    engine = sgtk.platform.current_engine()
    if engine is None:
        logger.warn('No engine is currently running.')
        return ''

    launch_app = engine.apps.get('tk-multi-launchapp')
    if launch_app is None:
        logger.warn('The engine {!r} must have tk-multi-launchapp configured in order to launch tk-aftereffectscc.'.format(engine.name))
        return ''

    adobe_framework = launch_app.frameworks.get('tk-framework-adobe')
    if adobe_framework is None:
        logger.warn('The app {!r} must have tk-framework-adobe configured in order to launch tk-aftereffectscc.'.format(launch_app.name))
        return ''

    return adobe_framework.disk_location


def compute_environment():
    """
    Return the env vars needed to launch the After Effects plugin.

    This will generate a dictionary of environment variables
    needed in order to launch the After Effects plugin.

    :returns: dictionary of env var string key/value pairs.
    """
    env = {}

    framework_location = _get_adobe_framework_location()
    if not os.path.exists(framework_location):
        raise EngineConfigurationError('The tk-framework-adobe could not be found in the current environment. Please check the log for more information.')

    # set the interpreter with which to launch the CC integration
    env["SHOTGUN_ADOBE_PYTHON"] = sys.executable
    env["SHOTGUN_ADOBE_FRAMEWORK_LOCATION"] = framework_location
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


