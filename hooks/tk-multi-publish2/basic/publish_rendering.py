# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import re
import shutil
import os
import sgtk
from sgtk.util.filesystem import ensure_folder_exists

HookBaseClass = sgtk.get_hook_baseclass()


class AfterEffectsCCRenderPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open nuke studio project.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_document.py"

    """

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = "https://support.shotgunsoftware.com/hc/en-us/articles/219033078"

        return """
        Publishes the file to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the file's current
        path on disk. Other users will be able to access the published file via
        the <b><a href='%s'>Loader</a></b> so long as they have access to
        the file's location on disk.

        If the document has not been saved, validation will fail and a button
        will be provided in the logging output to save the file.

        <h3>File versioning</h3>
        If the filename contains a version number, the process will bump the
        file to the next version after publishing.

        The <code>version</code> field of the resulting <b>Publish</b> in
        Shotgun will also reflect the version number identified in the filename.
        The basic worklfow recognizes the following version formats by default:

        <ul>
        <li><code>filename.v###.ext</code></li>
        <li><code>filename_v###.ext</code></li>
        <li><code>filename-v###.ext</code></li>
        </ul>

        After publishing, if a version number is detected in the file, the file
        will automatically be saved to the next incremental version number.
        For example, <code>filename.v001.ext</code> will be published and copied
        to <code>filename.v002.ext</code>

        If the next incremental version of the file already exists on disk, the
        validation step will produce a warning, and a button will be provided in
        the logging output which will allow saving the document to the next
        available version number prior to publishing.

        <br><br><i>NOTE: any amount of version number padding is supported.</i>

        <h3>Overwriting an existing publish</h3>
        A file can be published multiple times however only the most recent
        publish will be available to other users. Warnings will be provided
        during validation if there are previous publishes.
        """ % (loader_url,)

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # inherit the settings from the base publish plugin
        base_settings = \
            super(AfterEffectsCCRenderPublishPlugin, self).settings or {}

        # settings specific to this class
        aftereffects_publish_settings = {
            "Publish Sequence Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml. Please note, that the file "
                               "extension will be controlled by the option "
                               "'Default Output Module', so the template given "
                               "here should match the configured output-module.",
            },
            "Default Sequence Output Module": {
                "type": "str",
                "default": None,
                "description": "The output module to be chosen "
                               "in case no output module has "
                               "been set. This will control the "
                               "rendersettings.",
            },
            "Publish Movie Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml. Please note, that the file "
                               "extension will be controlled by the option "
                               "'Default Output Module', so the template given "
                               "here should match the configured output-module.",
            },
            "Default Movie Output Module": {
                "type": "str",
                "default": None,
                "description": "The output module to be chosen "
                               "in case no output module has "
                               "been set. This will control the "
                               "rendersettings.",
            },
        }

        # update the base settings
        base_settings.update(aftereffects_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["aftereffects.rendering"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
               all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """
        if not self.__is_acceptable(settings, item):
            return {"accepted": False}
        return {
                "accepted": True,
                "checked": True
            }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """
        if not self.__is_acceptable(settings, item):
            return False

        # run the base class validation
        return super(AfterEffectsCCRenderPublishPlugin, self).validate(
            settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        engine = self.parent.engine
        adobe = engine.adobe
        item.properties["publish_type"] = "Rendered Image"

        # in case we have no templates configured .. 
        if item.properties.get("no_render_no_copy", False):
            # we will register whatever paths
            # are set in the render_queue item
            for each_path in render_paths:
                item.properties["path"] = re.sub('\[#\+]', '#', each_path)
                super(AfterEffectsCCRenderPublishPlugin, self).publish(settings, item)
            return

        # in case we have templates

        # we get the neccessary settings
        queue_item = item.properties.get("queue_item")
        queue_item_index = item.properties.get("queue_item_index", "")
        render_on_publish = item.properties.get("render_on_publish")
        render_paths = item.properties.get("renderpaths", [])
        work_template = item.properties.get("work_template")

        render_seq_path_template_str = settings.get('Publish Sequence Template').value or ''
        render_seq_path_template = engine.tank.templates.get(render_seq_path_template_str)

        render_mov_path_template_str = settings.get('Publish Movie Template').value or ''
        render_mov_path_template = engine.tank.templates.get(render_mov_path_template_str)

        if render_on_publish:
            # render the queue item in case it is needed.
            if not self.__render_queue_item(queue_item):
                # if the render fails we will exit here.
                return

        # get the neccessary template fields from the..
        # ..work-template
        project_path = self.parent.engine.get_project_path()
        fields_from_work_template = work_template.get_fields(
                sgtk.util.ShotgunPath.normalize(project_path))

        # ..and from the queue_item.
        comp_name = "{}rq{}".format(queue_item.comp.name, queue_item_index)
        fields_from_work_template.update({
                "comp": re.sub("[^0-9a-zA-Z]", "", comp_name),
                "width": queue_item.comp.width,
                "height": queue_item.comp.height,
            })

        for each_path in render_paths:
            # get the path in a normalized state. no trailing separator, separators
            # are appropriate for current os, no double separators, etc.
            each_path = sgtk.util.ShotgunPath.normalize(each_path)

            # check whether the given path points to a sequence
            is_sequence = self.__path_is_sequence(each_path)

            # get the template to use depending if
            # the rendering is an image sequence or
            # a movie-container
            template = render_mov_path_template
            if is_sequence:
                template = render_seq_path_template
                fields_from_work_template['SEQ'] = '%{}d'.format(template.keys['SEQ'].format_spec)

            # build the target file path with formattable frame numbers
            abstract_target_path = template.apply_fields(fields_from_work_template)
            ensure_folder_exists(os.path.dirname(abstract_target_path))

            # copy the files to the publish location
            target_path = None
            for file_path, frame_no in self.__iter_render_files(each_path, queue_item):
                target_path = abstract_target_path
                if is_sequence:
                    target_path = abstract_target_path % frame_no
                shutil.copy2(file_path, target_path)

            # in case no file was copied, we skip
            # registering this publish path
            if target_path is None:
                continue

            # in case at least one file was copied,
            # we build an abstract target_path and
            # register that.
            item.properties["path"] = abstract_target_path
            super(AfterEffectsCCRenderPublishPlugin, self).publish(settings, item)

    def __render_queue_item(self, queue_item):
        """
        renders a given queue_item, by disabling all other queued items
        and only enabling the given item. After rendering the state of the
        render-queue is reverted.

        params:
            queue_item (adobe.RenderQueueItem): the item to be rendered
        returns (bool) successful rendering or not (True on success)
        """
        adobe = self.parent.engine.adobe

        # save the queue state for all unrendered items
        queue_item_state_cache = [(queue_item, queue_item.render)]
        for item in self.__iter_collection(adobe.app.project.renderQueue.items):
            # one cannot change the status on 
            if item.status != adobe.RQItemStatus.QUEUED:
                continue
            queue_item_state_cache.append((item, item.render))
            item.render = False

        success = False
        queue_item.render = True
        try:
            adobe.app.project.renderQueue.render()
            success = (queue_item.status == adobe.RQItemStatus.DONE)
        except Exception as e:
            self.logger.error(("Skipping item due to an error "
                    "while rendering: {}").format(e))
        finally:
            # reverting the original queued state for all
            # unprocessed items
            while queue_item_state_cache:
                item, status = queue_item_state_cache.pop(0)
                if item.status not in [adobe.RQItemStatus.DONE,
                                adobe.RQItemStatus.ERR_STOPPED,
                                adobe.RQItemStatus.RENDERING]:
                    item.render = status
        return success

    def __is_acceptable(self, settings, item):

        queue_item = item.properties.get("queue_item")
        render_paths = item.properties.get("renderpaths")
        set_render_path = item.properties.get("set_render_path")
        render_on_publish = item.properties.get("render_on_publish")
        work_template = item.properties.get("work_template")

        default_seq_output_module = settings.get('Default Sequence Output Module').value
        default_mov_output_module = settings.get('Default Movie Output Module').value
        render_seq_path_template_str = settings.get('Publish Sequence Template').value or ''
        render_mov_path_template_str = settings.get('Publish Movie Template').value or ''
        render_seq_path_template = self.parent.engine.tank.templates.get(render_seq_path_template_str)
        render_mov_path_template = self.parent.engine.tank.templates.get(render_mov_path_template_str)

        project_path = self.parent.engine.get_project_path()
        if not project_path:
            self.logger.warn("Project has to be saved in order to allow publishing renderings",
                    extra=self.__get_save_as_action())
            return False

        if not work_template and render_on_publish:
            self.logger.warn("One can only render on publish with a valid template configuration")
            return False

        for each_path in render_paths:
            item.properties["path"] = re.sub('\[#\+]', '#', each_path)
            break

        # check if the current configuration has templates assigned
        if not work_template and not render_on_publish:
            item.properties["no_render_no_copy"] = True
            return True

        # check configuration
        output_module_names = []
        for output_module in self.__iter_collection(queue_item.outputModules):
            output_module_names = list(output_module.templates)
            break
        if default_seq_output_module not in output_module_names:
            self.logger.warn(("The configured 'Default Sequence Output Module'"
                    "has to exist in After Effects. Please configure one of: {!r}\n"
                    "Given: {!r}").format(output_module_names, default_seq_output_module))
            return False

        if default_mov_output_module not in output_module_names:
            self.logger.warn(("The configured 'Default Movie Output Module'"
                    "has to exist in After Effects. Please configure one of: {!r}\n"
                    "Given: {!r}").format(output_module_names, default_mov_output_module))
            return False

        expected_missing_keys = ['comp', 'width', 'height']
        fields_from_work_template = work_template.get_fields(sgtk.util.ShotgunPath.normalize(project_path))
        missing_seq_keys = render_seq_path_template.missing_keys(fields_from_work_template)
        missing_mov_keys = render_mov_path_template.missing_keys(fields_from_work_template)
        if set(missing_seq_keys) - set(['SEQ'] + expected_missing_keys):
            self.logger.warn(("The file-path of this project must resolve "
                    "most all template fields of the 'Publish Sequence Template'. "
                    "The following keys can be ignored: {}.\nStill missing are: "
                    "{!r}\nPlease change the template or save to a different "
                    "context.").format(['SEQ'] + expected_missing_keys, missing_seq_keys))
            return False

        if set(missing_mov_keys) - set(expected_missing_keys):
            self.logger.warn(("The file-path of this project must resolve "
                    "most all template fields of the 'Publish Movie Template'. "
                    "The following keys can be ignored: {}.\nStill missing are: "
                    "{!r}\nPlease change the template or save to a different "
                    "context.").format(expected_missing_keys, missing_seq_keys))
            return False

        # this covers a theoretical situation, that there is no Output-Module assigned
        # this will almost never be the case, as it is not doable through the ui.
        if set_render_path and (not render_seq_path_template or not default_sequence_output_module):
            self.logger.warn("If no output-module is set, then Publish Template AND "
                        "Default Sequence Output Module have to be configured in order to be "
                        "publishable.")
            return False

        # in case the render queue item's status is DONE
        # we check if all files are there.
        if not render_on_publish:
            fix_render_on_publish = {
                        "action_button": {
                            "label": "Render On Publish...",
                            "tooltip": "",
                            "callback": lambda i=item: self.__change_item_settings(i, "render_on_publish", True)
                        }
                    }

            if not render_paths:
                self.logger.warn("Project has to be saved in order to allow publishing renderings",
                        extra=fix_render_on_publish)
                return False

            has_incomplete_renderings = False
            for each_path in render_paths:
                if not self.__check_sequence(each_path, queue_item):
                    has_incomplete_renderings = True
            if has_incomplete_renderings:
                self.logger.warn(("Render Queue item %s has incomplete renderings, "
                                  "but 'render on publish' is turned off. "
                                  "Please activate.") % (queue_item.comp.name,),
                        extra=fix_render_on_publish)
                return False

        # in case we will render before publishing we
        # have to check if the templates are matching
        for each_path in render_paths:
            path_template = render_seq_path_template
            output_module = default_seq_output_module
            if not self.__path_is_sequence(each_path):
                path_template = render_mov_path_template
                output_module = default_mov_output_module
            _, template_ext = os.path.splitext(path_template.definition)
            _, path_ext = os.path.splitext(each_path)
            if path_ext != template_ext:
                self.logger.warn(("The template extension {} is not matching"
                                  "the render output path extension for "
                                  "path {!r}").format(template_ext, each_path))
                return False

        return True

    def __path_is_sequence(self, path):
        if re.search(u"\[(#+)\]", path):
            return True
        return False

    def __iter_render_files(self, path, queue_item):
        # is the given render-path a sequence?
        match = re.search(u"\[(#+)\]", path)
        if not match:
            # if not, we just check if the file exists
            yield path, None
            raise StopIteration()

        # if yes, we check the existence of each frame
        frame_time = queue_item.comp.frameDuration
        start_time = int(round(queue_item.timeSpanStart / frame_time, 3))
        frame_numbers = int(round(queue_item.timeSpanDuration / frame_time, 3))
        skip_frames = queue_item.skipFrames + 1
        padding = len(match.group(1))

        test_path = path.replace(match.group(0), '%%0%dd' % padding)
        for frame_no in range(start_time, start_time+frame_numbers, skip_frames):
            yield test_path % frame_no, frame_no

    def __iter_collection(self, collection_item):
        for i in range(1, collection_item.length+1):
            yield collection_item[i]

    def __check_sequence(self, path, queue_item):
        for file_path, _ in self.__iter_render_files(path, queue_item):
            if not os.path.exists(file_path):
                return False
        return True

    def __change_item_settings(self, item, setting_name, value):
        item.properties[setting_name] = value

    def __get_save_as_action(self):
        """
        Simple helper for returning a log action dict for saving the project
        """

        engine = self.parent.engine

        # default save callback
        callback = lambda: engine.save_as()

        # if workfiles2 is configured, use that for file save
        if "tk-multi-workfiles2" in engine.apps:
            app = engine.apps["tk-multi-workfiles2"]
            if hasattr(app, "show_file_save_dlg"):
                callback = app.show_file_save_dlg

        return {
            "action_button": {
                "label": "Save As...",
                "tooltip": "Save the active project",
                "callback": callback
            }
        }
