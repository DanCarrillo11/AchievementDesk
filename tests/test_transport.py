from pathlib import Path
import tempfile
import unittest
from transport import GameClient, WorkerClient


class WorkerTests(unittest.TestCase):
    def test_demo_worker_read_apply_read(self):
        client = WorkerClient(0, demo=True)
        try:
            initial = client.receive()
            self.assertEqual(initial["account_id"], "DEMO")
            self.assertEqual(len(initial["achievements"]), 6)
            with tempfile.TemporaryDirectory() as folder:
                result = client.exchange(dict(command="apply", account_id="DEMO", snapshot_folder=folder,
                    changes=[dict(key="EXPLORER", before=False, after=True)]))
                self.assertEqual(result["result"]["status"], "confirmed")
                rows = client.exchange(dict(command="read"))["achievements"]
                self.assertTrue(next(a for a in rows if a["key"] == "EXPLORER")["unlocked"])
                self.assertEqual(len(list(Path(folder).glob("*.json"))), 1)
        finally:
            client.close()


class FakeWorker:
    def __init__(self, app_id, demo):
        self.app_id, self.demo = app_id, demo
        self.closed, self.sent = False, []
        self.read_error, self.exchange_error = False, False
        self.account_id = "test-account"

    def receive(self):
        if self.read_error:
            raise RuntimeError("Read failed")
        return dict(ok=True, account_id=self.account_id, achievements=[])

    def exchange(self, request):
        self.sent.append(request)
        if self.exchange_error:
            raise RuntimeError("Apply failed")
        return dict(ok=True, result={"status": "confirmed"})

    def close(self):
        self.closed = True


class OnDemandTests(unittest.TestCase):
    def setUp(self):
        self.workers = []
        self.prepare = lambda worker: None
        def factory(app_id, demo):
            worker = FakeWorker(app_id, demo)
            self.prepare(worker)
            self.workers.append(worker)
            return worker
        self.client = GameClient(123, worker_factory=factory)

    def test_no_connection_at_construction(self):
        self.assertEqual(self.workers, [])

    def test_read_closes_before_return(self):
        result = self.client.receive()
        self.assertEqual(result["account_id"], "test-account")
        self.assertTrue(self.workers[0].closed)
        self.assertEqual(self.workers[0].sent, [])

    def test_refresh_uses_new_short_session(self):
        self.client.receive()
        self.client.exchange(dict(command="read"))
        self.assertEqual(len(self.workers), 2)
        self.assertTrue(all(w.closed for w in self.workers))

    def test_apply_closes_before_return(self):
        request = dict(command="apply", account_id="test-account")
        self.client.exchange(request)
        self.assertEqual(self.workers[0].sent, [request])
        self.assertTrue(self.workers[0].closed)

    def test_read_failure_also_closes(self):
        self.prepare = lambda w: setattr(w, "read_error", True)
        with self.assertRaisesRegex(RuntimeError, "Read failed"):
            self.client.receive()
        self.assertTrue(self.workers[0].closed)

    def test_apply_failure_also_closes(self):
        self.prepare = lambda w: setattr(w, "exchange_error", True)
        with self.assertRaisesRegex(RuntimeError, "Apply failed"):
            self.client.exchange(dict(command="apply", account_id="test-account"))
        self.assertTrue(self.workers[0].closed)

    def test_account_switch_stops_before_write(self):
        with self.assertRaisesRegex(ValueError, "account changed"):
            self.client.exchange(dict(command="apply", account_id="other-account"))
        self.assertTrue(self.workers[0].closed)
        self.assertEqual(self.workers[0].sent, [])

    def test_invalid_operation_never_connects(self):
        with self.assertRaises(ValueError):
            self.client.exchange(dict(command="launch"))
        self.assertEqual(self.workers, [])

    def test_demo_changes_persist_without_native_session(self):
        client = GameClient(0, demo=True)
        try:
            client.receive()
            with tempfile.TemporaryDirectory() as folder:
                client.exchange(dict(command="apply", account_id="DEMO", snapshot_folder=folder,
                    changes=[dict(key="EXPLORER", before=False, after=True)]))
                rows = client.exchange(dict(command="read"))["achievements"]
                self.assertTrue(next(a for a in rows if a["key"] == "EXPLORER")["unlocked"])
        finally:
            client.close()

    def test_worker_rejects_unknown_command(self):
        client = WorkerClient(0, demo=True)
        try:
            client.receive()
            with self.assertRaisesRegex(RuntimeError, "Unknown"):
                client.exchange(dict(command="not-a-command"))
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
