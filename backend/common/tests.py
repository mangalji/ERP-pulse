from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone

from common import lazy_housekeeping


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

    @patch("common.lazy_housekeeping.run_scheduled_tasks", return_value={"sync": "failed"})
    def test_failed_worker_keeps_retry_lease_without_marking_success(self, run_tasks):
        today = timezone.localdate().isoformat()
        cache.add(lazy_housekeeping._LEASE_KEY, today, timeout=60)

        lazy_housekeeping._run_housekeeping(today, 120)

        self.assertIsNone(cache.get(lazy_housekeeping._SUCCESS_KEY))
        self.assertEqual(cache.get(lazy_housekeeping._LEASE_KEY), today)
        run_tasks.assert_called_once()
