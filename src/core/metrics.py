"""Prometheus metrics shared by HTTP and gRPC transports."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import grpc
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "ai_http_requests_total",
    "HTTP requests handled by the AI module.",
    ("method", "path", "status"),
)
HTTP_DURATION = Histogram(
    "ai_http_request_duration_seconds",
    "HTTP request latency.",
    ("method", "path"),
)
GRPC_REQUESTS = Counter(
    "ai_grpc_requests_total",
    "gRPC requests handled by the AI module.",
    ("method", "outcome"),
)
GRPC_DURATION = Histogram(
    "ai_grpc_request_duration_seconds",
    "gRPC request latency.",
    ("method",),
)


def _timed_unary(method: str, behavior: Callable) -> Callable:
    def wrapper(request, context):
        started = time.perf_counter()
        outcome = "ok"
        try:
            return behavior(request, context)
        except Exception:
            outcome = "error"
            raise
        finally:
            GRPC_REQUESTS.labels(method, outcome).inc()
            GRPC_DURATION.labels(method).observe(time.perf_counter() - started)

    return wrapper


def _timed_stream(method: str, behavior: Callable) -> Callable:
    def wrapper(request_or_iterator, context) -> Iterator:
        started = time.perf_counter()
        outcome = "ok"
        try:
            yield from behavior(request_or_iterator, context)
        except Exception:
            outcome = "error"
            raise
        finally:
            GRPC_REQUESTS.labels(method, outcome).inc()
            GRPC_DURATION.labels(method).observe(time.perf_counter() - started)

    return wrapper


class GrpcMetricsInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        method = handler_call_details.method
        common = {
            "request_deserializer": handler.request_deserializer,
            "response_serializer": handler.response_serializer,
        }
        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _timed_unary(method, handler.unary_unary), **common
            )
        if handler.unary_stream:
            return grpc.unary_stream_rpc_method_handler(
                _timed_stream(method, handler.unary_stream), **common
            )
        if handler.stream_unary:
            return grpc.stream_unary_rpc_method_handler(
                _timed_unary(method, handler.stream_unary), **common
            )
        if handler.stream_stream:
            return grpc.stream_stream_rpc_method_handler(
                _timed_stream(method, handler.stream_stream), **common
            )
        return handler
