import itertools
import threading
from socketserver import ThreadingMixIn


class NamedThreadingMixIn(ThreadingMixIn):
    """ThreadingMixIn whose workers are named PREFIX#N instead of Thread-N (process_request_thread)."""

    thread_prefix = "W#"

    def process_request(self, request, client_address):
        seq = vars(self).setdefault("_lrd_worker_seq", itertools.count(1))
        if self.block_on_close:
            from socketserver import _Threads

            vars(self).setdefault("_threads", _Threads())
        worker = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address),
            name=f"{self.thread_prefix}{next(seq)}",
            daemon=self.daemon_threads,
        )
        self._threads.append(worker)
        worker.start()
