# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import io
import unittest
import rpc_tests


def run_tests(engine):

    engine.logger.debug("Getting test suite...")
    suite = rpc_tests.get_tests_by_app_id(engine.app_id, engine.adobe)

    engine.logger.debug("Running test suite...")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)

    # Forward the full unittest output to the engine logger so it
    # appears in the sgtk log file and is not lost in stdout.
    for line in stream.getvalue().splitlines():
        if line.strip():
            engine.logger.info(line)

    # Log a clear summary at the end.
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    if result.wasSuccessful():
        engine.logger.info(
            "Tests PASSED: %d ran, %d failed, %d errors, %d skipped."
            % (total, failures, errors, skipped)
        )
    else:
        engine.logger.error(
            "Tests FAILED: %d ran, %d failed, %d errors, %d skipped."
            % (total, failures, errors, skipped)
        )
        for test, traceback in result.failures + result.errors:
            engine.logger.error("FAIL: %s\n%s" % (test, traceback))

    engine.logger.debug("Testing finished.")
