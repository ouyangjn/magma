"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import subprocess
import time
from unittest import TestCase
from unittest.mock import MagicMock

from magma.magmad.service_manager import ServiceState, ServiceManager

# Allow access to protected variables for unit testing
# pylint: disable=protected-access


class ServiceManagerSystemdTest(TestCase):
    """
    Tests for the service manager class using the systemd init system, and the
    service control sub-class. Can be run as integration tests by setting
    environment variable MAGMA_INTEGRATION_TEST=1.
    Must copy tests/dummy_service.service to /etc/systemd/system/ for
    integration tests to pass.
    """

    def setUp(self):
        """
        Run before each test
        """
        #  Only patch if this is a unit test. Otherwise create dummy mock so
        #  code that affects the mock can run.
        self.subprocess_mock = MagicMock(return_value='')
        if not os.environ.get('MAGMA_INTEGRATION_TEST'):
            subprocess.check_output = self.subprocess_mock

        #  Ensure test process is stopped
        self.dummy_service = ServiceManager.ServiceControl(
            name='dummy_service',
            init_system_spec=ServiceManager.SystemdInitSystem
        )
        self.dummy_service.stop_process()

    def tearDown(self):
        """
        Run after each test
        """
        #  Ensure test process is stopped
        self.dummy_service.stop_process()

    def test_process_start_stop(self):
        """
        Test that process can be started and stopped
        """
        self.subprocess_mock.return_value = 'unknown\n'
        self.assertEqual(self.dummy_service.status(), ServiceState.Unknown)

        self.subprocess_mock.return_value = 'active\n'
        self.dummy_service.start_process()
        time.sleep(1)  # Make sure that process doesnt immediately die
        self.assertEqual(self.dummy_service.status(), ServiceState.Active)

        self.subprocess_mock.return_value = 'unknown\n'
        self.dummy_service.stop_process()
        self.assertEqual(self.dummy_service.status(), ServiceState.Unknown)

    def test_service_manager_start_stop(self):
        """
        This test exercises the ServiceManager functions, but doesn't really
        verify functionality beyond the tests above
        """
        mgr = ServiceManager(['dummy1', 'dummy2'], init_system='systemd',
                             service_poller=MagicMock())

        mgr.start_services()
        self.subprocess_mock.return_value = 'active\n'
        self.assertEqual(mgr._service_control['dummy1'].status(),
                         ServiceState.Active)
        self.assertEqual(mgr._service_control['dummy2'].status(),
                         ServiceState.Active)

        mgr.stop_services()
        self.subprocess_mock.return_value = 'unknown\n'
        self.assertEqual(mgr._service_control['dummy1'].status(),
                         ServiceState.Unknown)
        self.assertEqual(mgr._service_control['dummy2'].status(),
                         ServiceState.Unknown)

    def test_dynamic_service_manager_start_stop(self):
        """
        This test exercises the ServiceManager functions, but doesn't really
        verify functionality beyond the tests above
        """
        mgr = ServiceManager(
            ['dummy1', 'dummy2'], 'systemd', MagicMock(), ['redirectd'], []
        )

        self.subprocess_mock.return_value = 'unknown\n'
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Unknown)

        mgr.update_dynamic_services(['redirectd'])
        self.subprocess_mock.return_value = 'active\n'
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Active)

        mgr.update_dynamic_services([])
        self.subprocess_mock.return_value = 'unknown\n'
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Unknown)


class ServiceManagerRunitTest(TestCase):
    """
    Tests for the service manager class using the runit init system, and the
    service control sub-class.
    """

    def setUp(self):
        """
        Run before each test
        """
        self.is_integration_test = bool(
            os.environ.get('MAGMA_INTEGRATION_TEST')
        )
        #  Only patch if this is a unit test. Otherwise create dummy mock so
        #  code that affects the mock can run.
        self.subprocess_mock = MagicMock(return_value='')
        if not self.is_integration_test:
            subprocess.check_output = self.subprocess_mock

        if not self.is_integration_test:
            self.dummy_service = ServiceManager.ServiceControl(
                name='dummy_service',
                init_system_spec=ServiceManager.RunitInitSystem,
            )
            self.dummy_service.stop_process()

    def tearDown(self):
        """
        Run after each test
        """
        #  Ensure test process is stopped
        if not self.is_integration_test:
            self.dummy_service.stop_process()

    def test_process_start_stop(self):
        """
        Test that runit process can be started and stopped
        """
        # Skip for integration tests, otherwise will fail on systems without
        # runit
        if self.is_integration_test:
            return

        self.subprocess_mock.return_value = (
            'down: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(self.dummy_service.status(),
                         ServiceState.Inactive)

        self.subprocess_mock.return_value = (
            'run: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.dummy_service.start_process()
        time.sleep(1)  # Make sure that process doesnt immediately die
        self.assertEqual(self.dummy_service.status(),
                         ServiceState.Active)

        self.subprocess_mock.return_value = (
            "fail: blabla: can't change to service directory: "
            "No such file or directory\n"
        )
        self.assertEqual(
            self.dummy_service.status(),
            ServiceState.Failed
        )

    def test_service_manager_start_stop(self):
        """
        This test exercises the ServiceManager functions, but doesn't really
        verify functionality beyond the tests above
        """
        # Skip for integration tests, otherwise will fail on systems without
        # runit
        if self.is_integration_test:
            return

        mgr = ServiceManager(['dummy1', 'dummy2'], init_system='runit',
                             service_poller=MagicMock())

        mgr.start_services()
        self.subprocess_mock.return_value = (
            'run: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(mgr._service_control['dummy1'].status(),
                         ServiceState.Active)
        self.assertEqual(mgr._service_control['dummy2'].status(),
                         ServiceState.Active)

        mgr.stop_services()
        self.subprocess_mock.return_value = (
            'down: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(mgr._service_control['dummy1'].status(),
                         ServiceState.Inactive)
        self.assertEqual(mgr._service_control['dummy2'].status(),
                         ServiceState.Inactive)

    def test_dynamic_service_manager_start_stop(self):
        """
        This test exercises the ServiceManager functions, but doesn't really
        verify functionality beyond the tests above
        """
        # Skip for integration tests, otherwise will fail on systems without
        # runit
        if self.is_integration_test:
            return

        mgr = ServiceManager(
            ['dummy1', 'dummy2'], 'runit', MagicMock(), ['redirectd'], []
        )

        self.subprocess_mock.return_value = (
            'down: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Inactive)

        mgr.update_dynamic_services(['redirectd'])
        self.subprocess_mock.return_value = (
            'run: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Active)

        mgr.update_dynamic_services([])
        self.subprocess_mock.return_value = (
            'down: e2e_controller: 268195s; run: log: (pid 2275) 268195s\n'
        )
        self.assertEqual(mgr._service_control['redirectd'].status(),
                         ServiceState.Inactive)
