# Running the tests

The `tk-aftereffects` tests are designed to be run within After Effects itself.

Follow these steps to run the tests.

1. Open a terminal, and set the `SHOTGUN_ADOBE_TESTS_ROOT` environment variable to point to this `tests` folder.
For example onn Mac: `export SHOTGUN_ADOBE_TESTS_ROOT=~/source_code/tk-aftereffects/tests`.
2. Enable debugging by setting `TK_DEBUG`, `export TK_DEBUG=1`.
3. Use the tank command to launch After Effects on a test project: `./tank after_effects_cc_2020`
4. Once launched and the "Shotgun Adobe Panel" is showing, choose "Run Tests" from the hamburger menu button.
5. The results of the tests can be seen in the console within After Effects. **Warning** there appears to be an issue with capturing the standard out, and sometime not all lines are recorded. You may need to run the tests a couple of time to ensure you get all output.
