# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import re
import os
import pprint
import tempfile
import uuid
import sys
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class AfterEffectsUploadVersionPlugin(HookBaseClass):
    """
    Plugin for sending aftereffects documents to shotgun for review.
    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(
            self.disk_location,
            os.pardir,
            "icons",
            "review.png"
        )

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Upload for review"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        publisher = self.parent

        shotgun_url = publisher.sgtk.shotgun_url

        media_page_url = "%s/page/media_center" % (shotgun_url,)
        review_url = "https://www.shotgunsoftware.com/features/#review"

        return """
        Upload the file to Shotgun for review.<br><br>

        A <b>Version</b> entry will be created in Shotgun and a transcoded
        copy of the file will be attached to it. The file can then be reviewed
        via the project's <a href='%s'>Media</a> page, <a href='%s'>RV</a>, or
        the <a href='%s'>Shotgun Review</a> mobile app.
        """ % (media_page_url, review_url, review_url)

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
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
        return {
            "Movie Output Module": {
                "type": "str",
                "default": "Lossless with Alpha",
                "description": "The output module to be chosen "
                               "in case no output module has "
                               "been set. This will control the "
                               "rendersettings.",
            }
        }

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """

        # we use "video" since that's the mimetype category.
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

        path = sgtk.util.ShotgunPath.normalize(self.parent.engine.get_project_path())

        if not path:
            # the project has not been saved before (no path determined).
            # provide a save button. the project will need to be saved before
            # validation will succeed.
            self.logger.warn(
                "The After Effects project has not been saved.",
                extra=self.__get_save_as_action()
            )

        if not self.__check_rendered_item(item):
            return {"accepted": True,
                    "checked": False
                    }

        if not self.__check_renderings(item):
            return {"accepted": False}

        self.logger.info(
            "After Effects '%s' plugin accepted." %
            (self.name,)
        )
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

        path = sgtk.util.ShotgunPath.normalize(self.parent.engine.get_project_path())

        if not path:
            # the project still requires saving. provide a save button.
            # validation fails.
            error_msg = "The After Effects project has not been saved."
            self.logger.error(
                error_msg,
                extra=self.__get_save_as_action()
            )
            raise Exception(error_msg)

        if not self.__check_rendered_item(item):
            return False

        if not self.__check_renderings(item):
            return False

        return True

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

    def __render_to_temp_location(self, queue_item, mov_output_module_template):

        temp_item = queue_item.duplicate()

        output_modules = list(self.__iter_collection(temp_item.outputModules))
        removable_output_modules = output_modules[1:]
        output_module = output_modules[0]

        output_module.applyTemplate(mov_output_module_template)
        _, ext = os.path.splitext(output_module.file.fsName)

        allocate_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        allocate_file.close()

        render_file = self.parent.engine.adobe.File(allocate_file.name)
        output_module.file = render_file

        while removable_output_modules:
            removable_output_modules.pop(0).remove()

        render_state = self.__render_queue_item(temp_item)

        temp_item.remove()
        if render_state:
            return allocate_file.name
        return ''

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        engine = publisher.engine

        queue_item = item.properties.get("queue_item")
        render_paths = item.properties.get("renderpaths")
        for each_path in render_paths:
            if not self.__path_is_sequence(each_path):
                upload_path = each_path
                break
        else:
            self.logger.info("About to render movie...")
            mov_output_module_template = settings.get('Movie Output Module').value
            upload_path = self.__render_to_temp_location(queue_item, mov_output_module_template)
            if not upload_path:
                self.logger.error("Rendering a movie failed. Cannot upload a version of this item.")
                return

        # use the path's filename as the publish name
        path_components = publisher.util.get_file_path_components(render_paths[0])
        publish_name = path_components["filename"]

        # populate the version data to send to SG
        self.logger.info("Creating Version...")
        version_data = {
            "project": item.context.project,
            "code": publish_name,
            "description": item.description,
            "entity": self._get_version_entity(item),
            "sg_task": item.context.task
        }

        publish_data = item.properties.get("sg_publish_data")

        # if the file was published, add the publish data to the version
        if publish_data:
            version_data["published_files"] = [publish_data]

        # log the version data for debugging
        self.logger.debug(
            "Populated Version data...",
            extra={
                "action_show_more_info": {
                    "label": "Version Data",
                    "tooltip": "Show the complete Version data dictionary",
                    "text": "<pre>%s</pre>" % (
                    pprint.pformat(version_data),)
                }
            }
        )

        # create the version
        self.logger.info("Creating version for review...")
        version = self.parent.shotgun.create("Version", version_data)

        # stash the version info in the item just in case
        item.properties["sg_version_data"] = version

        # on windows, ensure the path is utf-8 encoded to avoid issues with
        # the shotgun api
        if sys.platform.startswith("win"):
            upload_path = upload_path.decode("utf-8")

        # upload the file to SG
        self.logger.info("Uploading content...")
        self.parent.shotgun.upload(
            "Version",
            version["id"],
            upload_path,
            "sg_uploaded_movie"
        )
        self.logger.info("Upload complete!")

        item.properties["upload_path"] = upload_path

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        version = item.properties["sg_version_data"]

        self.logger.info(
            "Version uploaded for After Effects document",
            extra={
                "action_show_in_shotgun": {
                    "label": "Show Version",
                    "tooltip": "Reveal the version in Shotgun.",
                    "entity": version
                }
            }
        )

        upload_path = item.properties["upload_path"]

        # remove the tmp file
        if item.properties.get("remove_upload", False):
            try:
                os.remove(upload_path)
            except Exception:
                self.logger.warn(
                    "Unable to remove temp file: %s" % (upload_path,))
                pass

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

    def __check_rendered_item(self, item):
        queue_item = item.properties.get("queue_item")
        idx = item.properties.get("queue_item_index", '0')

        # as this plugin can only process rendered items,
        # we'll have to check if the given item is already
        # rendered. If not, we'll provide a render button.
        if queue_item.status != self.parent.engine.adobe.RQItemStatus.DONE:
            self.logger.warn("Render item is not Done yet. Please render it first.",
                        extra={
                        "action_button": {
                            "label": "Render Item {}".format(idx),
                            "tooltip": ("Render the queue item {} as"
                                       "movie, so it can be uploaded.").format(idx),
                            "callback": lambda qi=queue_item:self.__render_queue_item(qi)
                            }
                        }
                    )
            return False
        return True

    def __check_renderings(self, item):
        queue_item = item.properties.get("queue_item")
        render_paths = item.properties.get("renderpaths")
        has_incomplete_renderings = False
        for each_path in render_paths:
            if not self.__check_sequence(each_path, queue_item):
                has_incomplete_renderings = True

        if has_incomplete_renderings:
            self.logger.warn("Render Queue item has incomplete renderings, "
                              "please rerender this or duisable the queue item.")
            return False
        return True

    def _get_version_entity(self, item):
        """
        Returns the best entity to link the version to.
        """

        if item.context.entity:
            return item.context.entity
        elif item.context.project:
            return item.context.project
        else:
            return None

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

def _get_save_as_action(document):
    """
    Simple helper for returning a log action dict for saving the document
    """

    engine = sgtk.platform.current_engine()

    # default save callback
    callback = lambda: engine.save_as(document)

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current document",
            "callback": callback
        }
    }


def _document_path(document):
    """
    Returns the path on disk to the supplied document. May be ``None`` if the
    document has not been saved.
    """

    try:
        path = document.fullName.fsName
    except Exception:
        path = None

    return path
