# Copyright (c) 2017 Shotgun Software Inc.
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

HookBaseClass = sgtk.get_hook_baseclass()


class AfterEffectsCCSceneCollector(HookBaseClass):
    """
    Collector that operates on the current After Effects document. Should inherit
    from the basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

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

        # grab any base class settings
        collector_settings = \
            super(AfterEffectsCCSceneCollector, self).settings or {}

        # settings specific to this collector
        aftereffects_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                               "correspond to a template defined in "
                               "templates.yml. If configured, is made available"
                               "to publish plugins via the collected item's "
                               "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(aftereffects_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the open documents in After Effects and creates publish items
        parented under the supplied item.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        # go ahead and build the path to the icon for use by any documents
        icon_path = os.path.join(
            self.disk_location,
            os.pardir,
            "icons",
            "aftereffects.png"
        )

        publisher = self.parent
        engine = publisher.engine
        #document = engine.adobe.get_active_document()

        #if document:
        #    active_doc_name = document.name
        #else:
        #    engine.logger.debug("No active document found.")
        #    active_doc_name = None

        # attempt to retrive a configured work template. we can attach
        # it to the collected project items
        work_template_setting = settings.get("Work Template")
        work_template = None
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value)

        # FIXME: begin temporary workaround
        # we use different logic here only because we don't have proper support
        # for multi context workflows when templates are in play. So if we have
        # a work template configured, for now we'll only collect the current,
        # active document. Once we have proper multi context support, we can
        # remove this.
        if work_template:
            # same logic as the loop below but only processing the active doc
            if not document:
                return
            document_item = parent_item.create_item(
                "photoshop.document",
                "Photoshop Image",
                document.name
            )
            self.logger.info(
                "Collected Photoshop document: %s" % (document.name))
            document_item.set_icon_from_path(icon_path)
            document_item.thumbnail_enabled = False
            document_item.properties["document"] = document
            path = _document_path(document)
            if path:
                document_item.set_thumbnail_from_path(path)
            document_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for Photoshop collection.")
            return
        # FIXME: end temporary workaround

        # remember the current document. we need to switch documents while
        # collecting in order to get the proper context associated with each
        # item created.
        for i in range(engine.adobe.app.project.renderQueue.numItems):
            queue_item = engine.adobe.app.project.renderQueue.items[i+1]
            if queue_item.status not in [engine.adobe.RQItemStatus.QUEUED, engine.adobe.RQItemStatus.DONE]:
                continue

            
            render_path = 'path needs to be set.'
            if queue_item.status is not engine.adobe.RQItemStatus.NEEDS_OUTPUT and queue_item.numOutputModules:
                render_path = queue_item.outputModules[1].file.fsName
            comp_item_name = '{} - {}'.format(queue_item.comp.name, render_path)

            # create a publish item for the document
            comp_item = parent_item.create_item(
                "aftereffects.document",
                "After Effects Rendering",
                comp_item_name
            )
            comp_item.set_icon_from_path(icon_path)


            # disable thumbnail creation for After Effects documents. for the
            # default workflow, the thumbnail will be auto-updated after the
            # version creation plugin runs
            comp_item.thumbnail_enabled = False

            # add the document object to the properties so that the publish
            # plugins know which open document to associate with this item
            comp_item.properties["document"] = queue_item.outputModules[1].file

            self.logger.info("Collected After Effects document: %s" % (comp_item_name))

            # enable the rendered render queue items and expand it. other documents are
            # collapsed and disabled.
            if queue_item.status == engine.adobe.RQItemStatus.DONE:
                comp_item.expanded = True
                comp_item.checked = True
            else:
                # there is an active document, but this isn't it. collapse and
                # disable this item
                comp_item.expanded = False
                comp_item.checked = False

            path = None#_document_path(render_path)

            if path:
                # try to set the thumbnail for display. won't display anything
                # for psd/psb, but others should work.
                comp_item.set_thumbnail_from_path(path)

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            if work_template:
                comp_item.properties["work_template"] = work_template
                self.logger.debug(
                    "Work template defined for After Effects collection.")



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
