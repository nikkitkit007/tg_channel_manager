import logging
from threading import Lock
from time import time

import ecs_logging
import funcy
import structlog
from structlog.dev import plain_traceback
from structlog.processors import ExceptionRenderer
from structlog.stdlib import BoundLogger
from structlog.tracebacks import ExceptionDictTransformer

from app.config.settings import settings


LOG_MSG_LENGTH = 400


class ExcludeRouteFilter(logging.Filter):
    def __init__(self, routes: list[str]) -> None:
        super().__init__()
        self.routes = routes

    def filter(self, record: logging.LogRecord) -> bool:
        root = record.args[2]
        if funcy.any(root.startswith, self.routes):
            return record.args[4] >= LOG_MSG_LENGTH
        return super().filter(record)


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)


ecs_logs = settings.LOG.ECS_FORMAT
processors = [
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
    structlog.processors.CallsiteParameterAdder(
        {
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        },
    ),
]
if ecs_logs:
    processors += [ExceptionRenderer(ExceptionDictTransformer(locals_max_string=256))]
else:
    processors += [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]

renderer = (
    ecs_logging.StructlogFormatter()
    if ecs_logs
    else structlog.dev.ConsoleRenderer(exception_formatter=plain_traceback)
)
structlog.configure(
    processors=[*processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

handler = logging.StreamHandler()
handler.setFormatter(
    structlog.stdlib.ProcessorFormatter(
        processor=renderer, foreign_pre_chain=processors
    ),
)


def _init_logger(logger: logging.RootLogger) -> None:
    logger.addHandler(handler)
    logger.setLevel(settings.LOG.LEVEL)
    logging.captureWarnings(capture=True)


_init_logger(logging.getLogger())

logging.getLogger("sqlalchemy.engine").setLevel(settings.LOG.ALCHEMY)


class ProgressLog:
    def __init__(
        self, log_func: callable, total: int | None = None, log_every: int = 10
    ) -> None:
        self.rep_ts = self.start_ts = time()
        self.count = 0
        self.rep_count = 0
        self.log_every = log_every
        self.log_func = log_func
        self.total = total
        self.lock = Lock()

    def inc(self, size: int = 1) -> None:
        with self.lock:
            self.count += size
            ts = time()
            if ts - self.rep_ts >= self.log_every:
                self.log_func(
                    self.count,
                    (self.count - self.rep_count) * 1.0 / (ts - self.rep_ts),
                    self.count * 100.0 / self.total if self.total else None,
                )
                self.rep_ts = ts
                self.rep_count = self.count

    def get_stats(self) -> tuple[int, float, int]:
        total_time = max(time() - self.start_ts, 0.000001)
        return self.count, total_time, int(self.count / total_time)
