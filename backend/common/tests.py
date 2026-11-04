from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from requests import HTTPError

from common import lazy_housekeeping
from common.email_verification import ensure_email_deliverable, verify_email_deliverability


class LazyHousekeepingTests(SimpleTestCase):
    def setUp(self):
        cache.delete(lazy_housekeeping._SUCCESS_KEY)
        cache.delete(lazy_housekeeping._LEASE_KEY)

    def tearDown(self):
        cache.delete(lazy_housekeeping._SUCCESS_KEY)
        cache.delete(lazy_housekeeping._LEASE_KEY)

    @patch("common.lazy_housekeeping.threading.Thread")
    def test_starts_only_one_worker_for_today(self, thread_class):
        self.assertTrue(lazy_housekeeping.trigger_lazy_daily_housekeeping())
        self.assertFalse(lazy_housekeeping.trigger_lazy_daily_housekeeping())
        thread_class.assert_called_once()

    @patch("common.lazy_housekeeping.run_scheduled_tasks", return_value={"sync": "ok"})
    def test_successful_worker_marks_today_complete(self, run_tasks):
        today = timezone.localdate().isoformat()

        lazy_housekeeping._run_housekeeping(today, 120)

        self.assertEqual(cache.get(lazy_housekeeping._SUCCESS_KEY), today)
        self.assertIsNone(cache.get(lazy_housekeeping._LEASE_KEY))
        run_tasks.assert_called_once()


@override_settings(
    ABSTRACT_EMAIL_VALIDATION_API_KEY="abstract-test-key",
    HUNTER_API_KEY="hunter-test-key",
)
class EmailDeliverabilityVerificationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("common.email_verification.requests.get")
    def test_abstract_deliverable_result_is_used_without_hunter_call(self, get):
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={
                "email_deliverability": {"status": "deliverable", "status_detail": "valid_email"}
            }),
        )

        result = verify_email_deliverability("person@example.com")

        self.assertTrue(result["is_deliverable"])
        self.assertEqual(result["provider"], "abstract")
        self.assertEqual(get.call_count, 1)

    @patch("common.email_verification.requests.get")
    def test_quota_or_provider_error_falls_back_to_hunter(self, get):
        abstract_failure = Mock()
        abstract_failure.raise_for_status.side_effect = HTTPError("429 quota exceeded")
        hunter_success = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"data": {"status": "valid"}}),
        )
        get.side_effect = [abstract_failure, hunter_success]

        result = verify_email_deliverability("fallback@example.com")

        self.assertTrue(result["is_deliverable"])
        self.assertEqual(result["provider"], "hunter")
        self.assertEqual(get.call_count, 2)

    @patch("common.email_verification.requests.get")
    def test_confirmed_undeliverable_email_is_blocked_and_cached(self, get):
        get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={
                "email_deliverability": {"status": "undeliverable", "status_detail": "invalid_email"}
            }),
        )

        with self.assertRaisesMessage(ValueError, "Please enter a valid, active email address."):
            ensure_email_deliverable("invalid@example.com")
        result = verify_email_deliverability("invalid@example.com")

        self.assertTrue(result["should_block"])
        self.assertEqual(get.call_count, 1)

    @patch("common.lazy_housekeeping.run_scheduled_tasks", return_value={"sync": "failed"})
    def test_failed_worker_keeps_retry_lease_without_marking_success(self, run_tasks):
        today = timezone.localdate().isoformat()
        cache.add(lazy_housekeeping._LEASE_KEY, today, timeout=60)

        lazy_housekeeping._run_housekeeping(today, 120)

        self.assertIsNone(cache.get(lazy_housekeeping._SUCCESS_KEY))
        self.assertEqual(cache.get(lazy_housekeeping._LEASE_KEY), today)
        run_tasks.assert_called_once()
