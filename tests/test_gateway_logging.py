"""Offline R1 regressions through stock HTTPX, AnyIO and asyncio diagnostics."""
import asyncio
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import errno
import json
import logging
from pathlib import Path
import socket
import tempfile
import threading
import traceback
import unittest
from unittest.mock import patch

import httpx

from grepbit.gateway import GatewayClient, GatewayConfig, MODEL, ModelError, _PRIVATE_TRANSPORT
from grepbit.model import interpret_and_execute
from tools.fixture import build


HOST = "r1-gateway.invalid"
ADDRESS = "192.0.2.81"
KEY = "dummy-r1-credential-Q7"
OTHER_HOST = "r1-unrelated.invalid"
OTHER_ADDRESS = "198.51.100.82"
BASE = "http://" + HOST + "/v1"
ECHO = " ".join((HOST, ADDRESS, KEY))
MESSAGES = [
    {"role": "system", "content": "Use the supplied semantic context."},
    {"role": "user", "content": "Count confirmed bookings in March 2026."},
]
APP = logging.getLogger("r1.benign.application")
LOGGER_NAMES = (
    "asyncio", "httpx", "httpcore", "httpcore.connection", "httpcore.http11",
    "httpcore.http2", "httpcore.proxy", "httpcore.socks", APP.name,
)


class _CapturedLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def text(self):
        return "\n".join(self.format(record) for record in self.records)


@dataclass(frozen=True)
class _LogOrigin:
    name: str
    module: str
    funcName: str
    levelno: int


class _EmissionProbe(logging.Filter):
    """Observe only origin, context and level before production filters."""

    def __init__(self):
        super().__init__()
        self.records = []

    def filter(self, record):
        origin = _LogOrigin(record.name, record.module, record.funcName, record.levelno)
        self.records.append((origin, _PRIVATE_TRANSPORT.get()))
        return True


class _MemorySocket:
    def __init__(self, boundary, family, type, proto):
        self.boundary = boundary
        self.family, self.type, self.proto = family, type, proto
        self.closed = False
        self.blocking = True

    def __repr__(self):
        return f"<MemorySocket peer={self.getpeername()!r}>"

    def fileno(self):
        return -1

    def setblocking(self, value):
        self.blocking = value

    def gettimeout(self):
        return None if self.blocking else 0

    def connect(self, address):
        self.boundary.connections.append((address, _PRIVATE_TRANSPORT.get()))
        self.boundary.test.assertEqual(address, (ADDRESS, 80))
        if self.boundary.failure == "tcp":
            raise OSError(errno.ECONNREFUSED, ECHO)

    def getpeername(self):
        return (ADDRESS, 80)

    def getsockname(self):
        return ("192.0.2.82", 49152)

    def close(self):
        self.closed = True


class _MemoryHTTPTransport(asyncio.Transport):
    def __init__(self, boundary, sock, protocol, waiter):
        super().__init__({"socket": sock, "peername": sock.getpeername(),
                          "sockname": sock.getsockname()})
        self.boundary, self.sock, self.protocol = boundary, sock, protocol
        self.closed = False
        self.request = bytearray()
        self.responded = False
        self.paused = False
        self.pending_response = False
        boundary.loop.call_soon(protocol.connection_made, self)
        boundary.loop.call_soon(waiter.set_result, None)

    def set_write_buffer_limits(self, high=None, low=None):
        pass

    def pause_reading(self):
        self.paused = True

    def resume_reading(self):
        self.paused = False
        if self.pending_response:
            self.boundary.loop.call_soon(self._deliver)

    def write(self, data):
        self.request.extend(data)
        if self.responded or b"\r\n\r\n" not in self.request:
            return
        headers, body = bytes(self.request).split(b"\r\n\r\n", 1)
        lengths = [line.split(b":", 1)[1].strip() for line in headers.split(b"\r\n")
                   if line.lower().startswith(b"content-length:")]
        self.boundary.test.assertEqual(len(lengths), 1)
        if len(body) < int(lengths[0]):
            return
        self.boundary.test.assertEqual(len(body), int(lengths[0]))
        self.boundary.requests.append((headers, json.loads(body)))
        self.responded = self.pending_response = True
        self.boundary.loop.call_soon(self._deliver)

    def _deliver(self):
        if self.pending_response and not self.paused and not self.closed:
            self.pending_response = False
            self.protocol.data_received(self.boundary.response)

    def write_eof(self):
        pass

    def is_closing(self):
        return self.closed

    def close(self):
        if not self.closed:
            self.closed = True
            self.sock.close()
            self.boundary.loop.call_soon(self.protocol.connection_lost, None)

    def abort(self):
        self.close()


class _Boundary:
    def __init__(self, test, loop, *, failure=None, blocked=False):
        self.test, self.loop, self.failure, self.blocked = test, loop, failure, blocked
        self.release = threading.Event()
        self.started = asyncio.Event()
        self.finished = asyncio.Event()
        self.submitted = []
        self.worker_contexts = []
        self.worker_threads = []
        self.dns_queries = []
        self.connections = []
        self.requests = []
        self.sockets = []
        self.transports = []
        self.capture = _CapturedLogs()
        self.probe = _EmissionProbe()
        self.client = GatewayClient(GatewayConfig(BASE, KEY))
        self.executor = loop.run_in_executor
        self.main_thread = threading.get_ident()
        self.body = json.dumps({
            "model": MODEL,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "reasoning_content": ECHO,
                "content": json.dumps({"outcome": "request", "request": {
                    "metrics": ["confirmed_booking_count"],
                    "start": "2026-03-01T00:00:00+08:00",
                    "end": "2026-04-01T00:00:00+08:00",
                    "timezone": "Asia/Taipei",
                }}),
            }}],
        }).encode("ascii")
        status = "401 Unauthorized" if failure == "http" else "200 OK"
        self.response = (
            f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(self.body)}\r\nX-R1-Echo: {ECHO}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii") + self.body

    def getaddrinfo(self, host, port, family=0, type=0, proto=0, flags=0):
        name = host.decode("ascii") if isinstance(host, bytes) else host
        if name not in (HOST, OTHER_HOST) or port != 80:
            return self.real_dns(host, port, family, type, proto, flags)
        self.dns_queries.append((name, port))
        APP.info("benign application in DNS executor")
        self.loop.call_soon_threadsafe(self.started.set)
        if self.blocked and not self.release.wait(timeout=5):
            raise AssertionError("Test did not release the DNS worker.")
        APP.info("benign application leaving DNS executor")
        if self.failure == "dns":
            raise socket.gaierror(socket.EAI_NONAME, ECHO)
        address = ADDRESS if name == HOST else OTHER_ADDRESS
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]

    def run_in_executor(self, executor, function, *args):
        self.submitted.append(function)
        APP.info("benign application during request")

        def invoke_original():
            self.worker_contexts.append(_PRIVATE_TRANSPORT.get())
            self.worker_threads.append(threading.get_ident())
            try:
                return function(*args)
            finally:
                # The original stdlib wrapper has logged its result before this signal.
                self.loop.call_soon_threadsafe(self.finished.set)

        return self.executor(executor, invoke_original)

    def socket(self, family=-1, type=-1, proto=-1, fileno=None):
        self.test.assertEqual(family, socket.AF_INET)
        self.test.assertEqual(type, socket.SOCK_STREAM)
        self.test.assertIsNone(fileno)
        sock = _MemorySocket(self, family, type, proto)
        self.sockets.append(sock)
        return sock

    def make_transport(self, sock, protocol, waiter):
        self.test.assertEqual(type(protocol).__module__, "anyio._backends._asyncio")
        self.test.assertEqual(type(protocol).__name__, "StreamProtocol")
        transport = _MemoryHTTPTransport(self, sock, protocol, waiter)
        self.transports.append(transport)
        return transport

    def run(self, coroutine):
        return self.loop.run_until_complete(asyncio.wait_for(coroutine, timeout=4))

    def emitted(self, name, function):
        return [(record, private) for record, private in self.probe.records
                if record.name == name and record.funcName == function]


class GatewayLoggingTests(unittest.TestCase):
    @contextmanager
    def network(self, *, debug, failure=None, blocked=False):
        # The event loop's own socketpair is created before any socket patches.
        loop = asyncio.new_event_loop()
        loop.set_debug(debug)
        boundary = _Boundary(self, loop, failure=failure, blocked=blocked)
        try:
            with ExitStack() as stack:
                loggers = [logging.getLogger(name) for name in LOGGER_NAMES]
                for logger in loggers:
                    old = (logger.level, logger.handlers[:], logger.propagate)

                    def restore(logger=logger, old=old):
                        logger.removeFilter(boundary.probe)
                        logger.setLevel(old[0])
                        logger.handlers[:] = old[1]
                        logger.propagate = old[2]

                    stack.callback(restore)
                    logger.setLevel(logging.DEBUG)
                    logger.handlers[:] = [boundary.capture]
                    logger.propagate = False
                    logger.filters.insert(0, boundary.probe)
                levels = [logger.level for logger in loggers]
                root_level = logging.getLogger().level
                disabled = logging.Logger.manager.disable
                guards = []
                for target in (
                    "socket.socket.connect", "socket.socket.connect_ex",
                    "socket.create_connection", "socket.getaddrinfo",
                    "socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr",
                ):
                    guard = stack.enter_context(patch(
                        target, side_effect=AssertionError("Real network access is forbidden.")))
                    guards.append(guard)
                    if target == "socket.getaddrinfo":
                        boundary.real_dns = guard
                stack.enter_context(patch("socket.getaddrinfo", new=boundary.getaddrinfo))
                stack.enter_context(patch("socket.socket", new=boundary.socket))
                stack.enter_context(patch.object(loop, "_make_socket_transport",
                                                new=boundary.make_transport))
                stack.enter_context(patch.object(loop, "run_in_executor",
                                                new=boundary.run_in_executor))
                state_guards = [
                    stack.enter_context(patch(target, side_effect=AssertionError(
                        "Production must not change logging state.")))
                    for target in ("logging.disable", "logging.Logger.setLevel")
                ]
                state_guards.append(stack.enter_context(patch.object(
                    loop, "set_debug", side_effect=AssertionError(
                        "Production must not change event-loop debug mode."))))
                try:
                    yield boundary
                finally:
                    boundary.release.set()
                    if boundary.submitted:
                        boundary.run(boundary.finished.wait())
                    boundary.run(loop.shutdown_default_executor())
                    for guard in guards + state_guards:
                        guard.assert_not_called()
                    self.assertEqual([logger.level for logger in loggers], levels)
                    self.assertEqual(logging.getLogger().level, root_level)
                    self.assertEqual(logging.Logger.manager.disable, disabled)
                    self.assertIs(loop.get_debug(), debug)
                    self.assertFalse(_PRIVATE_TRANSPORT.get())
                    self.assertTrue(all(sock.closed for sock in boundary.sockets))
                    self.assertTrue(all(item.closed for item in boundary.transports))
        finally:
            loop.close()

    def assert_private(self, text):
        for canary in (HOST, ADDRESS, KEY, OTHER_HOST, OTHER_ADDRESS):
            self.assertNotIn(canary, text)

    def assert_stock_path(self, boundary, *, connected):
        self.assertIsNone(boundary.client._transport)
        self.assertEqual(boundary.client.http_attempts, 1)
        self.assertEqual(boundary.dns_queries, [(HOST, 80)])
        self.assertEqual(boundary.worker_contexts, [False])
        self.assertNotEqual(boundary.worker_threads, [boundary.main_thread])
        self.assertEqual(len(boundary.submitted), 1)
        dns_records = boundary.emitted("asyncio", "_getaddrinfo_debug")
        connection_records = boundary.emitted("asyncio", "create_connection")
        if boundary.loop.get_debug():
            self.assertIs(boundary.submitted[0].__func__,
                          asyncio.BaseEventLoop._getaddrinfo_debug)
            self.assertEqual(len(dns_records), 1 if boundary.failure == "dns" else 2)
            self.assertTrue(all(record.module == "base_events" and not private
                                for record, private in dns_records))
            self.assertEqual(dns_records[0][0].levelno, logging.DEBUG)
            self.assertEqual(len(connection_records), int(connected))
            if connected:
                self.assertEqual(connection_records[0][0].module, "base_events")
                self.assertEqual(connection_records[0][0].levelno, logging.DEBUG)
                self.assertTrue(connection_records[0][1])
        else:
            self.assertEqual(boundary.submitted[0], boundary.getaddrinfo)
            self.assertEqual(dns_records, [])
            self.assertEqual(connection_records, [])
        if connected:
            self.assertEqual(boundary.connections, [((ADDRESS, 80), True)])
            self.assertEqual(len(boundary.requests), 1)
            headers, body = boundary.requests[0]
            self.assertTrue(headers.startswith(b"POST /v1/chat/completions HTTP/1.1\r\n"))
            self.assertIn(("Authorization: Bearer " + KEY).encode("ascii"), headers)
            self.assertEqual(body["model"], MODEL)
            trace_records = [(record, private) for record, private in boundary.probe.records
                             if record.name == "httpcore.http11"]
            self.assertTrue(trace_records)
            self.assertTrue(all(record.levelno == logging.DEBUG and private
                                for record, private in trace_records))
        APP.info("benign application after return")
        logging.getLogger("asyncio").debug("benign non-DNS asyncio after return")
        text = boundary.capture.text()
        for marker in ("benign application during request", "benign application in DNS executor",
                       "benign application leaving DNS executor", "benign application after return",
                       "benign non-DNS asyncio after return"):
            self.assertIn(marker, text)
        self.assertTrue(any(record.name == APP.name and record.funcName == "run_in_executor"
                            and private
                            for record, private in boundary.probe.records))

    def test_stock_http_success_preserves_fact_pack_and_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fixture.sqlite"
            build(database)
            for debug in (False, True):
                with self.subTest(debug=debug), self.network(debug=debug) as boundary:
                    result = boundary.run(interpret_and_execute(
                        MESSAGES[1]["content"], database, boundary.client, timeout_seconds=3))
                    self.assertIsNone(result.error)
                    self.assertIsNotNone(result.request)
                    self.assertIsNotNone(result.fact_pack)
                    self.assertEqual(result.request.metrics, ("confirmed_booking_count",))
                    self.assertEqual([fact.value for fact in result.fact_pack.facts], [7])
                    self.assertEqual(result.evidence["http_status"], 200)
                    self.assertEqual(result.evidence["client_http_attempts"], 1)
                    self.assertEqual(result.evidence["transport_security"], "unencrypted_http")
                    self.assertEqual(set(result.evidence["stages"].values()), {"passed"})
                    self.assertEqual(result.evidence["fact_pack"],
                                     json.loads(json.dumps(result.fact_pack.to_dict())))
                    self.assert_private(json.dumps(result.evidence))
                    self.assert_stock_path(boundary, connected=True)
                    self.assert_private(boundary.capture.text())

    def test_dns_tcp_and_http_errors_are_safe_and_private(self):
        for debug in (False, True):
            for failure in ("dns", "tcp", "http"):
                with self.subTest(debug=debug, failure=failure), self.network(
                        debug=debug, failure=failure) as boundary:
                    with self.assertRaises(ModelError) as caught:
                        boundary.run(boundary.client.complete(MESSAGES))
                    error = caught.exception
                    self.assertEqual(error.code, "auth_failed" if failure == "http"
                                     else "transport_error")
                    self.assertEqual(error.http_status, 401 if failure == "http" else None)
                    self.assert_private(str(error))
                    self.assert_private(repr(error))
                    self.assert_private("".join(traceback.format_exception(error)))
                    self.assert_stock_path(boundary, connected=failure == "http")
                    if failure == "tcp":
                        self.assertEqual(boundary.connections, [((ADDRESS, 80), True)])
                    self.assert_private(boundary.capture.text())

    async def late_dns(self, boundary, *, cancel):
        task = asyncio.create_task(boundary.client.complete(
            MESSAGES, timeout_seconds=3 if cancel else 0.2))
        try:
            await asyncio.wait_for(boundary.started.wait(), timeout=2)
            if cancel:
                # Force the stdlib's slow-DNS INFO branch without changing loop settings.
                await asyncio.sleep(0.15)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            else:
                with self.assertRaises(ModelError) as caught:
                    await asyncio.wait_for(task, timeout=2)
                self.assertEqual(caught.exception.code, "timeout")
                self.assert_private("".join(traceback.format_exception(caught.exception)))
            self.assertTrue(task.done())
            self.assertFalse(boundary.finished.is_set())
            self.assertFalse(boundary.release.is_set())
            self.assertEqual(boundary.worker_contexts, [False])
            self.assertFalse(_PRIVATE_TRANSPORT.get())
            APP.info("benign application after coroutine cleanup")
            before_release = len(boundary.emitted("asyncio", "_getaddrinfo_debug"))
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            boundary.release.set()
            if boundary.submitted:
                await asyncio.wait_for(boundary.finished.wait(), timeout=2)
        self.assertTrue(boundary.finished.is_set())
        self.assertEqual(boundary.connections, [])
        self.assert_stock_path(boundary, connected=False)
        if boundary.loop.get_debug():
            late = boundary.emitted("asyncio", "_getaddrinfo_debug")[before_release:]
            self.assertEqual(len(late), 1)
            self.assertEqual(late[0][0].levelno, logging.INFO)
            self.assertFalse(late[0][1])
        self.assert_private(boundary.capture.text())

    def test_timeout_keeps_executor_dns_private_after_coroutine_cleanup(self):
        for debug in (False, True):
            with self.subTest(debug=debug), self.network(debug=debug, blocked=True) as boundary:
                boundary.run(self.late_dns(boundary, cancel=False))

    def test_cancellation_keeps_executor_dns_private_after_coroutine_cleanup(self):
        for debug in (False, True):
            with self.subTest(debug=debug), self.network(debug=debug, blocked=True) as boundary:
                boundary.run(self.late_dns(boundary, cancel=True))

    def test_dns_suppression_is_process_lifetime_and_metadata_scoped(self):
        with self.network(debug=True) as boundary:
            boundary.run(boundary.client.complete(MESSAGES))
            self.assert_stock_path(boundary, connected=True)
            before_unrelated = len(boundary.emitted("asyncio", "_getaddrinfo_debug"))
            result = boundary.run(boundary.loop.getaddrinfo(
                OTHER_HOST, 80, type=socket.SOCK_STREAM))
            self.assertEqual(result[0][4], (OTHER_ADDRESS, 80))
            unrelated = boundary.emitted("asyncio", "_getaddrinfo_debug")[before_unrelated:]
            self.assertEqual(len(unrelated), 2)
            self.assertTrue(all(record.module == "base_events" and not private
                                for record, private in unrelated))
            self.assertEqual(boundary.dns_queries, [(HOST, 80), (OTHER_HOST, 80)])
            self.assertEqual(boundary.worker_contexts, [False, False])
            for name, module, function in (
                (APP.name, "base_events", "_getaddrinfo_debug"),
                ("asyncio", "not_base_events", "_getaddrinfo_debug"),
                ("asyncio", "base_events", "not_getaddrinfo_debug"),
            ):
                logger = logging.getLogger(name)
                marker = f"benign scope control {name} {module} {function}"
                record = logger.makeRecord(name, logging.INFO, module + ".py", 1,
                                           marker, (), None, func=function)
                logger.handle(record)
                self.assertIn(marker, boundary.capture.text())
            self.assert_private(boundary.capture.text())

    def test_unprotected_stock_http_and_connection_diagnostics_still_work(self):
        for debug in (False, True):
            with self.subTest(debug=debug), self.network(debug=debug) as boundary:
                boundary.run(boundary.client.complete(MESSAGES))
                self.assert_stock_path(boundary, connected=True)
                boundary.capture.records.clear()

                async def unprotected_request():
                    async with httpx.AsyncClient(trust_env=False) as client:
                        return await client.post(BASE + "/chat/completions", json={})

                response = boundary.run(unprotected_request())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["x-r1-echo"], ECHO)
                self.assertEqual(response.content, boundary.body)
                records = boundary.capture.records
                self.assertTrue(any(record.name == "httpx" and record.levelno == logging.INFO
                                    and HOST in record.getMessage() for record in records))
                self.assertTrue(any(record.name == "httpcore.http11"
                                    and ECHO in record.getMessage() for record in records))
                header_records = [
                    record.getMessage() for record in records
                    if record.name == "httpcore.http11"
                    and "receive_response_headers.complete" in record.getMessage()
                ]
                self.assertEqual(len(header_records), 1)
                self.assertIn(ECHO, header_records[0])
                connections = [record for record in records if record.name == "asyncio"
                               and record.funcName == "create_connection"]
                self.assertEqual(len(connections), int(debug))
                if debug:
                    self.assertIn(ADDRESS, connections[0].getMessage())


if __name__ == "__main__":
    unittest.main()
