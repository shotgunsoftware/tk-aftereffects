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
    Plugin for publishing after effects renderings.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_rendering.py"

    """

    REJECTED, PARTIALLY_ACCEPTED, FULLY_ACCEPTED = range(3)

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = "https://support.shotgunsoftware.com/hc/en-us/articles/219033078"

        return """
        Publishes Render Queue elements to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the file's current
        path on disk. Other users will be able to access the published file via
        the <b><a href='%s'>Loader</a></b> so long as they have access to
        the file's location on disk.

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
            "Check Output Module": {
                "type": "bool",
                "default": True,
                "description": "Indicates, wether to check the "
                               "output module name of the given "
                               "render queue item. If 'Force "
                               "Output Module' is not set, don't "
                               "check the item.",
            },
            "Force Output Module": {
                "type": "bool",
                "default": True,
                "description": "Indicates, wether the configured "
                               "output module should be enforced, "
                               "in case the output module check "
                               "failed.",
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
        if self.__is_acceptable(settings, item) is self.REJECTED:
            return {"accepted": False}
        elif self.__is_acceptable(settings, item) is self.PARTIALLY_ACCEPTED:
            return {
                "accepted": True,
                "checked": False
            }
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
        if self.__is_acceptable(settings, item) is not self.FULLY_ACCEPTED:
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
        render_paths = item.properties.get("renderpaths", [])

        # in case we have no templates configured .. 
        if item.properties.get("no_render_no_copy", False):
            # we will register whatever paths
            # are set in the render_queue item
            for each_path in render_paths:
                item.properties["path"] = re.sub('\[#\+]', '#', each_path)
                super(AfterEffectsCCRenderPublishPlugin, self).publish(settings, item)

            # without templates we will exit here
            return

        # in case we have templates

        # we get the neccessary settings
        queue_item = item.properties.get("queue_item")
        queue_item_index = item.properties.get("queue_item_index", "")
        render_on_publish = item.properties.get("render_on_publish")
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

        published_renderings = item.parent.properties.get("published_renderings", [])

        for each_path in self.__iter_publishable_paths(
                            queue_item,
                            queue_item_index,
                            render_paths,
                            work_template,
                            render_mov_path_template,
                            render_seq_path_template):
            item.properties["path"] = each_path
            super(AfterEffectsCCRenderPublishPlugin, self).publish(settings, item)
            published_renderings.append(item.properties.get("sg_publish_data"))

    def __is_acceptable(self, settings, item):
        """
        This method is a helper to decide, whether the current publish item
        is valid. it is called from the validate and the accept method.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: int indicating the acceptance-level. One of
            REJECTED, PARTIALLY_ACCEPTED, FULLY_ACCEPTED
        """

        queue_item = item.properties.get("queue_item")
        render_paths = item.properties.get("renderpaths")
        set_render_path = item.properties.get("set_render_path")
        render_on_publish = item.properties.get("render_on_publish")
        work_template = item.properties.get("work_template")
        project_path = sgtk.util.ShotgunPath.normalize(self.parent.engine.get_project_path())

        default_seq_output_module = settings.get('Default Sequence Output Module').value
        default_mov_output_module = settings.get('Default Movie Output Module').value
        render_seq_path_template_str = settings.get('Publish Sequence Template').value or ''
        render_mov_path_template_str = settings.get('Publish Movie Template').value or ''
        check_output_module = settings.get('Check Output Module').value
        force_output_module = settings.get('Force Output Module').value

        render_seq_path_template = self.parent.engine.tank.templates.get(render_seq_path_template_str)
        render_mov_path_template = self.parent.engine.tank.templates.get(render_mov_path_template_str)

        # set the item path to some temporary value
        for each_path in render_paths:
            item.properties["path"] = re.sub('\[#\+]', '#', each_path)
            break

        if queue_item is None:
            self.logger.warn(("No queue_item was set. This is most likely due to "
                        "a mismatch of the collector and this publish-plugin."))
            return self.REJECTED

        if not project_path:
            self.logger.warn("Project has to be saved in order to allow publishing renderings",
                    extra=self.__get_save_as_action())
            return self.REJECTED
        
        # check if the current configuration has templates assigned
        if not work_template:
            if render_on_publish:
                self.logger.warn("One can only render on publish with a valid template configuration")
                return self.REJECTED
            item.properties["no_render_no_copy"] = True
            return self.PARTIALLY_ACCEPTED

        # we now know, that we have templates available, so we can do extended checking

        # check output module configuration
        om_state = self.__output_modules_acceptable(
                        queue_item,
                        default_mov_output_module,
                        default_seq_output_module,
                        check_output_module,
                        force_output_module
                    )
        if om_state != self.FULLY_ACCEPTED:
            return om_state

        # check template configuration
        t_state = self.__templates_acceptable(
                        work_template,
                        render_seq_path_template,
                        render_mov_path_template,
                        project_path
                    )
        if t_state != self.FULLY_ACCEPTED:
            return t_state

        # this covers a theoretical situation, that there is no Output-Module assigned
        # this will almost never be the case, as it is not doable through the ui.
        if set_render_path and (not render_seq_path_template or not default_sequence_output_module):
            self.logger.warn("If no output-module is set, then Publish Template AND "
                        "Default Sequence Output Module have to be configured in order to be "
                        "publishable.")
            return self.REJECTED

        # in case the render queue item's status is DONE
        # we check if all files are there.
        if not render_on_publish:
            rf_state = self.__render_files_existing(item, queue_item, render_paths)
            if rf_state != self.FULLY_ACCEPTED:
                return rf_state

        # in case we will render before publishing we
        # have to check if the templates are matching
        ext_state = self.__template_extension_match_render_paths(
                        render_paths,
                        render_seq_path_template,
                        render_mov_path_template,
                    )
        if ext_state != self.FULLY_ACCEPTED:
            return ext_state

        return self.FULLY_ACCEPTED

    def __template_extension_match_render_paths(self, render_paths, seq_template, mov_template):
        """
        Helper method to verify that the template extensions are matching the
        extensions of the render paths. This helper is called during verification
        and acceptance checking.

        :param render_paths: list of strings describing after-effects style render files. Sequences are marked like [####]
        :param seq_template: publish template for image-sequences
        :param mov_template: publish template for movie-clips
        """

        for each_path in render_paths:
            path_template = mov_template
            if self.__path_is_sequence(each_path):
                path_template = seq_template

            _, template_ext = os.path.splitext(path_template.definition)
            _, path_ext = os.path.splitext(each_path)

            if path_ext != template_ext:
                self.logger.warn(("The template extension {} is not matching"
                                  "the render output path extension for "
                                  "path {!r}").format(template_ext, each_path))
                return self.REJECTED
        return self.FULLY_ACCEPTED

    def __templates_acceptable(self, work_template, seq_template,
                mov_template, project_path):
        """
        Helper method to verify that the configured templates are valid.
        To do this, this method checks for the missing keys when initial fields
        were calculated from the current work-file. If the number of keys doesn't
        exceed the expected number the test passes.
        This helper is called during verification and acceptance checking.

        :param work_template: template matching the current work scene
        :param seq_template: publish template for image-sequences
        :param mov_template: publish template for movie-clips
        :param project_path: str file path to the current work file
        """
        expected_missing_keys = ['comp', 'width', 'height']
        msg = ("The file-path of this project must resolve "
               "most all template fields of the 'Publish {} Template'. "
               "The following keys can be ignored: {}.\nStill missing are: "
               "{!r}\nPlease change the template or save to a different "
               "context.")

        fields_from_work_template = work_template.get_fields(project_path)

        missing_seq_keys = seq_template.missing_keys(fields_from_work_template)
        missing_mov_keys = mov_template.missing_keys(fields_from_work_template)

        if set(missing_seq_keys) - set(['SEQ'] + expected_missing_keys):
            self.logger.warn(msg.format('Sequence', ['SEQ'] + expected_missing_keys, missing_seq_keys))
            return self.REJECTED

        if set(missing_mov_keys) - set(expected_missing_keys):
            self.logger.warn(msg.format('Movie', expected_missing_keys, missing_mov_keys))
            return self.REJECTED

        return self.FULLY_ACCEPTED

    def __render_files_existing(self, publish_item, queue_item, render_paths):
        """
        Helper that verifies, that all render-files are actually existing on disk.

        :param publish_item: the item, which is about to be published by the publisher
        :param queue_item: an after effects render-queue-item
        :param render_paths: list of strings describing after-effects style render files. Sequences are marked like [####]
        """
        fix_render_on_publish = {
                    "action_button": {
                        "label": "Render On Publish...",
                        "tooltip": "",
                        "callback": lambda i=publish_item: self.__change_item_settings(i, "render_on_publish", True)
                    }
                }

        if not render_paths:
            self.logger.warn("Project has to be saved in order to allow publishing renderings",
                    extra=fix_render_on_publish)
            return self.REJECTED

        has_incomplete_renderings = False
        for each_path in render_paths:
            if not self.__check_sequence(each_path, queue_item):
                has_incomplete_renderings = True
        if has_incomplete_renderings:
            self.logger.warn(("Render Queue item %s has incomplete renderings, "
                              "but 'render on publish' is turned off. "
                              "Please activate.") % (queue_item.comp.name,),
                    extra=fix_render_on_publish)
            return self.REJECTED
        return self.FULLY_ACCEPTED

    def __output_modules_acceptable(self, queue_item, mov_template, seq_template, check=True, force=True):
        """
        Helper that verifies, that all the output modules are configured correctly.
        It will perform extended checking if check is True. This means, that
        each output-module will be compared with the configured output module templates.
        In case force is not set verification will fail if the latter check fails, if
        force is set, the output-module will be set to the configured template.

        :param queue_item: an after effects render-queue-item
        :param mov_template: str name of the output module template for movie-clips
        :param seq_template: str name of the output module template for image-sequences
        :param check: bool indicating if extended checking should be performed (see above)
        :param force: bool indicating that a fix should be applied in case extended checking fails
        """
        # check configuration
        output_module_names = []
        for i, output_module in enumerate(self.__iter_collection(queue_item.outputModules)):

            # first we check if the configured templates are actually existing
            # in after effects or not.
            if not i:
                output_module_names = list(output_module.templates)
                msg = ("The configured output module has to exist in After Effects. "
                    "Please configure one of: {!r}\nYou configured: {!r}")
                if seq_template not in output_module_names:
                    self.logger.warn(msg.format(output_module_names, seq_template))
                    return self.REJECTED
                if mov_template not in output_module_names:
                    self.logger.warn(msg.format(output_module_names, mov_template))
                    return self.REJECTED

            # for extra security, we check, wether the output module
            # is pointing to a valid file. This should only fail in
            # race conditions
            if output_module.file == None:
                self.logger.warn(("There render queue item contains an "
                        "output module, that has no output file set."
                        "Please set a file to the output module no {}").format(i))
                return self.REJECTED

            # getting the template to use for this output module.
            template_name = mov_template
            if self.__path_is_sequence(output_module.file.fsName):
                template_name = seq_template

            # if we don't check or the check is OK, we can continue
            if not check or output_module.name == template_name:
                continue

            # if the fix output module is configured, we can apply the fix
            # and continue
            fix_output_module = lambda om=output_module, t=template_name: om.applyTemplate(t)
            if force:
                self.logger.info("Forcing Output Module to follow template {!r}".format(template_name))
                fix_output_module()
                continue

            self.logger.warn(
                        ("Output Module template {!r} doesn't "
                         "match the configured one {!r}.").format(
                                  output_module.name, template_name),
                        extra={
                        "action_button": {
                            "label": "Force Output Module...",
                            "tooltip": "Sets the template on the output module.",
                            "callback": fix_output_module,
                        }
                    })
            return self.PARTIALLY_ACCEPTED
        return self.FULLY_ACCEPTED

    def __path_is_sequence(self, path):
        """
        Helper to query if an adobe-style render path is
        describing a sequence.

        :param path: str filepath to check
        :returns: bool True if the path describes a sequence
        """
        if re.search(u"\[(#+)\]", path):
            return True
        return False

    def __check_sequence(self, path, queue_item):
        """
        Helper to query if all render files of a given queue item
        are actually existing.

        :param path: str filepath to check
        :param queue_item: an after effects render queue item
        :returns: bool True if the path describes a sequence
        """
        for file_path, _ in self.__iter_render_files(path, queue_item):
            if not os.path.exists(file_path):
                return False
        return True

    def __iter_collection(self, collection_item):
        """
        Helper to iter safely through an adobe-collection item
        as its index starts at 1, not 0.

        :param collection_item: the after-effects collection item to iter
        :yields: the next child item of the collection
        """
        for i in range(1, collection_item.length+1):
            yield collection_item[i]

    def __iter_render_files(self, path, queue_item):
        """
        Yields all render-files and its frame number of a given
        after effects render queue item.

        :param path: str filepath to check
        :param queue_item: an after effects render queue item
        :yields: 2-item-tuple where the firstitem is the resolved path (str)
                of the render file and the second item the frame-number or
                None if the path is not an image-sequence.
        """
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

    def __iter_publishable_paths(self, queue_item, queue_item_idx, render_paths, work_template, mov_template, seq_template):
        """
        Helper method to copy and iter all renderfiles to the configured publish location

        :param queue_item: the render queue item
        :param queue_item_idx: integer, that describes the number of the queue_item in the after effects render queue. 
        :param render_paths: list of strings describing after-effects style render files. Sequences are marked like [####]
        :param work_template: the template for the current work-file 
        :param mov_template: the publish template for movie-clips
        :param seq_template: the publish template for image-sequences
        :yields: an abstract render-file-path (str) that has a format expression (like %04d) at the frame numbers position 
        """

        # get the neccessary template fields from the..
        # ..work-template
        project_path = self.parent.engine.get_project_path()
        fields_from_work_template = work_template.get_fields(
                sgtk.util.ShotgunPath.normalize(project_path))

        # ..and from the queue_item.
        comp_name = "{}rq{}".format(queue_item.comp.name, queue_item_idx)
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
            template = mov_template
            if is_sequence:
                template = seq_template
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
            yield abstract_target_path

    def __render_queue_item(self, queue_item):
        """
        renders a given queue_item, by disabling all other queued items
        and only enabling the given item. After rendering the state of the
        render-queue is reverted.

        :param queue_item: the adobe.RenderQueueItem to be rendered
        :returns: bool indicating successful rendering or not
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
            self.logger.debug("Start rendering..")
            adobe.app.project.renderQueue.render()
        except Exception as e:
            self.logger.error(("Skipping item due to an error "
                    "while rendering: {}").format(e))

        # reverting the original queued state for all
        # unprocessed items
        while queue_item_state_cache:
            item, status = queue_item_state_cache.pop(0)
            if item.status not in [adobe.RQItemStatus.DONE,
                            adobe.RQItemStatus.ERR_STOPPED,
                            adobe.RQItemStatus.RENDERING]:
                item.render = status

        # we check for success if the render queue item status
        # has changed to DONE
        success = (queue_item.status == adobe.RQItemStatus.DONE)
        return success

    def __change_item_settings(self, item, setting_name, value):
        """
        Helper as item assignment doesn't work in lambdas

        :param item: item to be published from the publisher
        :param setting_name: str of the setting name
        :param value: value to set the given setting to
        """
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
