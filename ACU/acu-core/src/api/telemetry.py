"""
OpenTelemetry initialization and setup for distributed tracing.
"""

from fastapi import FastAPI

from src.config.settings import system_config
from src.utils.logger import log


def setup_telemetry(app: FastAPI):
    """
    Configure and instrument OpenTelemetry for the FastAPI app.

    This sets up a global tracer provider, configures an OTLP exporter,
    and instruments FastAPI and requests libraries.
    """
    if not getattr(system_config, "telemetry_enabled", False):
        log.info("Telemetría OpenTelemetry desactivada (ACU_TELEMETRY_ENABLED=false)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        log.info("Iniciando configuración de OpenTelemetry...")

        resource = Resource.create(
            {
                "service.name": system_config.project_name.lower(),
                "service.version": system_config.version,
            }
        )

        provider = TracerProvider(resource=resource)

        otlp_endpoint = getattr(
            system_config, "otlp_endpoint", "http://jaeger:4318/v1/traces"
        )
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        RequestsInstrumentor().instrument()

        log.info(
            f"OpenTelemetry instrumentado correctamente enviando a {otlp_endpoint}"
        )
    except ImportError as e:
        log.warning(f"No se pudo inicializar OpenTelemetry: faltan dependencias ({e})")


def get_tracer(name: str):
    """Get a tracer instance for manual span creation."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        # Dummy tracer
        class DummySpan:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def set_attribute(self, *args, **kwargs):
                pass

            def set_status(self, *args, **kwargs):
                pass

            def record_exception(self, *args, **kwargs):
                pass

        class DummyTracer:
            def start_as_current_span(self, *args, **kwargs):
                return DummySpan()

        return DummyTracer()
