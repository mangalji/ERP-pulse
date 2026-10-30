import json
from unittest import TestCase
from unittest.mock import patch

from common.timing import _current_span, timed_stage


class StageTimingTests(TestCase):
    def test_nested_stages_share_trace_and_safe_ids_with_exact_duration(self):
        @timed_stage("child")
        def child(secret):
            return 42

        @timed_stage("parent")
        def parent(*, document_id, payload):
            return child(payload)

        with patch("common.timing.perf_counter", side_effect=[10, 11, 12, 14]):
            with self.assertLogs("performance", level="INFO") as logs:
                self.assertEqual(parent(document_id="doc-1", payload="private-invoice"), 42)
        child_event, parent_event = [json.loads(record.getMessage()[7:]) for record in logs.records]
        self.assertEqual(child_event["duration_ms"], 1000)
        self.assertEqual(parent_event["duration_ms"], 4000)
        self.assertEqual(child_event["trace_id"], parent_event["trace_id"])
        self.assertEqual(child_event["parent_span_id"], parent_event["span_id"])
        self.assertEqual(child_event["document_id"], "doc-1")
        self.assertNotIn("private-invoice", str(logs.output))
        self.assertIsNone(_current_span.get())

    def test_exception_is_preserved_and_context_is_reset(self):
        failure = ValueError("sensitive provider response")

        @timed_stage("failure")
        def fail():
            raise failure

        with self.assertLogs("performance", level="INFO") as logs:
            with self.assertRaises(ValueError) as caught:
                fail()
        self.assertIs(caught.exception, failure)
        event = json.loads(logs.records[0].getMessage()[7:])
        self.assertEqual(event["outcome"], "raised")
        self.assertEqual(event["error_type"], "ValueError")
        self.assertNotIn("sensitive provider response", str(logs.output))
        self.assertIsNone(_current_span.get())

    def test_business_failure_return_is_not_labelled_success(self):
        @timed_stage("validation")
        def validate():
            return {"valid": False}

        with self.assertLogs("performance", level="INFO") as logs:
            self.assertEqual(validate(), {"valid": False})
        self.assertEqual(json.loads(logs.records[0].getMessage()[7:])["outcome"], "returned")

    def test_broken_log_handler_does_not_break_workflow(self):
        @timed_stage("work")
        def work():
            return 42

        with patch("common.timing.logger.isEnabledFor", return_value=True):
            with patch("common.timing.logger.info", side_effect=RuntimeError("logging failure")):
                self.assertEqual(work(), 42)
        self.assertIsNone(_current_span.get())

    def test_disabled_logging_skips_timer(self):
        @timed_stage("work")
        def work():
            return 42

        with patch("common.timing.logger.isEnabledFor", return_value=False):
            with patch("common.timing.perf_counter") as clock:
                self.assertEqual(work(), 42)
                clock.assert_not_called()
