""" unittests for strategy.py """
import unittest
import ddt
import mock

from django.test import TestCase

from third_party_auth.strategy import ConfigurationModelStrategy
from third_party_auth.tests import testutil


@ddt.ddt
@mock.patch('student.views.create_account_with_params')
@unittest.skipUnless(testutil.AUTH_FEATURE_ENABLED, 'third_party_auth not enabled')
class TestStrategy(TestCase):
    """ Unit tests for authentication strategy """
    def setUp(self):
        super(TestStrategy, self).setUp()
        self.request_mock = mock.Mock()
        self.strategy = ConfigurationModelStrategy(mock.Mock(), request=self.request_mock)

    def _get_last_call_args(self, patched_create_account):
        """ Helper to get last call arguments from a mock """
        args, unused_kwargs = patched_create_account.call_args
        return args

    def test_create_user_sets_tos_and_honor_code(self, patched_create_account):
        self.strategy.create_user(username='myself')

        self.assertTrue(patched_create_account.called)
        request, user_data = self._get_last_call_args(patched_create_account)

        self.assertEqual(request, self.request_mock)
        self.assertTrue(user_data['terms_of_service'])
        self.assertTrue(user_data['honor_code'])

    @ddt.data(
        (None, 'Fallback Name', 'Fallback Name'),
        ('q', 'Other Name', 'Other Name'),
        ('q2', 'Other Name', 'q2'),
        ('qwe', 'Other Name', 'qwe'),
        ('user1', 'Fallback Name', 'user1')
    )
    @ddt.unpack
    def test_create_user_sets_name(self, full_name, fallback_name, expected_name, patched_create_account):
        with mock.patch.object(self.strategy, 'setting', mock.Mock()) as patched_setting:
            patched_setting.return_value = fallback_name
            self.strategy.create_user(username='myself', fullname=full_name)

            # it is actually always called, but this assertion is relaxed to allow not actually going to settings
            # if there's no point in that
            if expected_name == fallback_name:
                self.assertIn(mock.call("THIRD_PARTY_AUTH_FALLBACK_FULL_NAME"), patched_setting.mock_calls)

        _, user_data = self._get_last_call_args(patched_create_account)
        self.assertEqual(user_data['name'], expected_name)

    def test_sets_password_if_missing(self, patched_create_account):
        self.strategy.create_user(username='myself', fullname='myself')
        _, user_data = self._get_last_call_args(patched_create_account)

        self.assertIn('password', user_data)

    @ddt.data(
        (None, False),
        ('q', False),
        ('12', False),
        ('456', True),
        ('$up3r_$e(ur3_p/|$$w0rd', True),
    )
    @ddt.unpack
    def test_passes_password_if_specified(self, password, should_match, patched_create_account):
        self.strategy.create_user(username='myself', fullname='myself', password=password)
        _, user_data = self._get_last_call_args(patched_create_account)

        self.assertIn('password', user_data)
        if should_match:
            self.assertEqual(user_data['password'], password)

    @ddt.data(
        (None, 'fallback_domain.com', 'myself@fallback_domain.com'),
        ('', 'other_domain.com', 'myself@other_domain.com'),
        ('qwe@asd.com', 'fallback_domain.com', 'qwe@asd.com'),
        ('zxc@darpa.gov.mil.edu', 'fallback_domain.com', 'zxc@darpa.gov.mil.edu'),
    )
    @ddt.unpack
    def test_sets_email_if_not_provided(self, email, fallback_domain, expected_email, patched_create_account):
        with mock.patch.object(self.strategy, 'setting', mock.Mock()) as patched_setting:
            patched_setting.return_value = fallback_domain
            # fullname is needed to avoid calling setting twice
            self.strategy.create_user(username='myself', fullname='myself', email=email)

            # it is actually always called, but this assertion is relaxed to allow not actually going to settings
            # if there's no point in that
            if email != expected_email:
                self.assertIn(mock.call("FAKE_EMAIL_DOMAIN"), patched_setting.mock_calls)

        _, user_data = self._get_last_call_args(patched_create_account)
        self.assertEqual(user_data['email'], expected_email)

    @ddt.data(
        (True, None, 'host', 'host'),
        (True, "", 'other_host', 'other_host'),
        (True, 'x_forwarded_host', 'irrelevant', 'x_forwarded_host'),
        (True, 'other_x_forwarded_host', 'still_irrelevant', 'other_x_forwarded_host'),
        (False, None, 'host', 'host'),
        (False, "", 'other_host', 'other_host'),
        (False, 'x_forwarded_host', 'normal_host', 'normal_host'),
        (False, 'other_x_forwarded_host', 'other_normal_host', 'other_normal_host'),
    )
    @ddt.unpack
    def test_request_host(self, respect_x_headers, x_forwarded_value, get_host_value, expected_value, unused_patch):
        self.request_mock.META = {}
        self.request_mock.get_host.return_value = get_host_value
        if x_forwarded_value is not None:
            self.request_mock.META['HTTP_X_FORWARDED_HOST'] = x_forwarded_value

        with self.settings(RESPECT_X_FORWARDED_HEADERS=respect_x_headers):
            self.assertEqual(self.strategy.request_host(), expected_value)

    @ddt.data(
        (True, None, 'port', 'port'),
        (True, "", 'other_port', 'other_port'),
        (True, 'x_forwarded_port', 'irrelevant', 'x_forwarded_port'),
        (True, 'other_x_forwarded_port', 'still_irrelevant', 'other_x_forwarded_port'),
        (False, None, 'port', 'port'),
        (False, "", 'other_port', 'other_port'),
        (False, 'x_forwarded_port', 'normal_port', 'normal_port'),
        (False, 'other_x_forwarded_port', 'other_normal_port', 'other_normal_port'),
    )
    @ddt.unpack
    def test_request_port(self, respect_x_headers, x_forwarded_value, server_port_value, expected_value, unused_patch):
        self.request_mock.META = {'SERVER_PORT': server_port_value}
        if x_forwarded_value is not None:
            self.request_mock.META['HTTP_X_FORWARDED_PORT'] = x_forwarded_value

        with self.settings(RESPECT_X_FORWARDED_HEADERS=respect_x_headers):
            self.assertEqual(self.strategy.request_port(), expected_value)
