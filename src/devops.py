"""Matha DevOps 工具：CI/CD、监控、日志、服务发现。"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CIStage(Enum):
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"
    NOTIFY = "notify"
    CLEAN = "clean"


class CIStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    PENDING = "pending"
    CANCELLED = "cancelled"


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Pipeline:
    name: str
    stages: list[CIStage] = field(default_factory=list)
    status: CIStatus = CIStatus.PENDING
    result: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    logs: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


@dataclass
class Job:
    name: str
    stage: CIStage
    commands: list[str] = field(default_factory=list)
    status: CIStatus = CIStatus.PENDING
    output: str = ""
    error: str = ""
    duration: float = 0.0


@dataclass
class LogEntry:
    level: LogLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    name: str
    metric_type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Alert:
    level: AlertLevel
    message: str
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    notifications: list[str] = field(default_factory=list)


class PipelineRunner:
    """CI/CD 流水线运行器。"""

    def __init__(self, name: str):
        self.name = name
        self.pipeline = Pipeline(name=name)
        self._jobs: list[Job] = []
        self._workspace = os.getcwd()

    def add_stage(self, stage: CIStage, commands: list[str]) -> Job:
        job = Job(name=f"{stage.value}", stage=stage, commands=commands)
        self._jobs.append(job)
        return job

    def run(self) -> Pipeline:
        self.pipeline.status = CIStatus.RUNNING
        self.pipeline.started_at = time.time()
        for job in self._jobs:
            job.status = CIStatus.RUNNING
            start = time.time()
            try:
                result = subprocess.run(
                    job.commands, shell=True, capture_output=True, text=True
                )
                job.output = result.stdout
                job.error = result.stderr
                job.status = CIStatus.SUCCESS if result.returncode == 0 else CIStatus.FAILED
            except Exception as e:
                job.error = str(e)
                job.status = CIStatus.FAILED
            job.duration = time.time() - start
            self.pipeline.logs.append(f"{job.name}: {job.status.value}")

        all_success = all(j.status == CIStatus.SUCCESS for j in self._jobs)
        self.pipeline.status = CIStatus.SUCCESS if all_success else CIStatus.FAILED
        self.pipeline.finished_at = time.time()
        return self.pipeline


class LogAggregator:
    """日志聚合器。"""

    def __init__(self):
        self._logs: collections.deque = collections.deque(maxlen=100000)
        self._filters: list[Callable] = []
        self._formatters: list[Callable] = []

    def write(self, level: LogLevel, message: str,
               source: str = "") -> None:
        entry = LogEntry(level=level, message=message, source=source)
        self._logs.append(entry)

    def query(self, level: LogLevel | None = None,
               source: str | None = None,
               limit: int = 100) -> list[LogEntry]:
        results = []
        for entry in reversed(self._logs):
            if level and entry.level != level:
                continue
            if source and entry.source != source:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def watch(self, callback: Callable) -> None:
        self._filters.append(callback)

    def format(self, entry: LogEntry) -> str:
        return f"[{entry.level.value}] {entry.timestamp:.3f} {entry.source}: {entry.message}"


class MetricsCollector:
    """指标收集器。"""

    def __init__(self):
        self._metrics: dict[str, Metric] = {}
        self._histograms: dict[str, list[float]] = {}

    def record(self, name: str, value: float,
                metric_type: MetricType = MetricType.GAUGE,
                labels: dict[str, str] = None) -> None:
        self._metrics[name] = Metric(
            name=name, metric_type=metric_type,
            value=value, labels=labels or {},
        )

    def histogram(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def get_metric(self, name: str) -> Metric | None:
        return self._metrics.get(name)

    def summary(self) -> dict[str, Any]:
        return {
            "metrics": len(self._metrics),
            "histograms": len(self._histograms),
            "timestamp": time.time(),
        }


class AlertManager:
    """告警管理器。"""

    def __init__(self):
        self._alerts: list[Alert] = []
        self._rules: list[dict[str, Any]] = []
        self._notifiers: list[Callable] = []

    def add_alert(self, level: AlertLevel, message: str,
                    source: str = "") -> Alert:
        alert = Alert(level=level, message=message, source=source)
        self._alerts.append(alert)
        return alert

    def add_rule(self, condition: str,
                    action: str, level: AlertLevel = AlertLevel.WARNING) -> None:
        self._rules.append({"condition": condition, "action": action, "level": level})

    def evaluate(self) -> list[Alert]:
        triggered = []
        for rule in self._rules:
            alert = self.add_alert(rule["level"], rule["action"], "rule")
            triggered.append(alert)
        return triggered

    def notify(self, alert: Alert) -> None:
        for notifier in self._notifiers:
            notifier(alert)
        alert.notifications = [f"notified_{i}" for i in range(len(self._notifiers))]

    def add_notifier(self, notifier: Callable) -> None:
        self._notifiers.append(notifier)


class HealthCheck:
    """健康检查。"""

    def __init__(self):
        self._checks: dict[str, dict[str, Any]] = {}
        self._ready = True
        self._alive = True

    def register(self, name: str, check: Callable,
                 interval: float = 30.0) -> None:
        self._checks[name] = {"check": check, "interval": interval, "last": 0}

    def check(self) -> bool:
        for name, info in self._checks.items():
            try:
                result = info["check"]()
                if not result:
                    self._ready = False
                    return False
            except Exception:
                self._ready = False
                return False
        return True

    def is_ready(self) -> bool:
        return self._ready

    def is_alive(self) -> bool:
        return self._alive


class ServiceDiscovery:
    """服务发现。"""

    def __init__(self):
        self._services: dict[str, dict[str, Any]] = {}
        self._health_checks: dict[str, bool] = {}

    def register(self, name: str, address: str,
                 port: int, metadata: dict[str, Any] = None) -> None:
        self._services[name] = {
            "address": address, "port": port,
            "metadata": metadata or {},
            "registered_at": time.time(),
        }
        self._health_checks[name] = True

    def deregister(self, name: str) -> bool:
        self._services.pop(name, None)
        self._health_checks.pop(name, None)
        return True

    def discover(self, name: str) -> dict[str, Any] | None:
        return self._services.get(name)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._services.values())

    def get_healthy(self) -> list[dict[str, Any]]:
        return [s for s, h in self._health_checks.items() if h and s in self._services]


class ConfigManager:
    """配置管理器。"""

    def __init__(self):
        self._config: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}

    def load(self, path: str) -> bool:
        try:
            with open(path) as f:
                self._config = json.load(f)
            return True
        except Exception:
            return False

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def get_env(self, key: str, default: str = "") -> str:
        return os.environ.get(key, default)


def create_pipeline_runner(name: str) -> PipelineRunner:
    return PipelineRunner(name=name)


def create_log_aggregator() -> LogAggregator:
    return LogAggregator()


def create_metrics_collector() -> MetricsCollector:
    return MetricsCollector()


def create_alert_manager() -> AlertManager:
    return AlertManager()


def create_health_check() -> HealthCheck:
    return HealthCheck()


def create_service_discovery() -> ServiceDiscovery:
    return ServiceDiscovery()


def create_config_manager() -> ConfigManager:
    return ConfigManager()


# ============================================================
# 内置注册
# ============================================================

def _register_devops(builtins: dict) -> None:
    builtins["创建流水线运行器"] = create_pipeline_runner
    builtins["创建日志聚合器"] = create_log_aggregator
    builtins["创建指标收集器"] = create_metrics_collector
    builtins["创建告警管理器"] = create_alert_manager
    builtins["创建健康检查"] = create_health_check
    builtins["创建服务发现"] = create_service_discovery
    builtins["创建配置管理器"] = create_config_manager


def _devops_names() -> list[str]:
    return ["创建流水线运行器", "创建日志聚合器",
            "创建指标收集器", "创建告警管理器",
            "创建健康检查", "创建服务发现",
            "创建配置管理器"]


__all__ = [
    "CIStage", "CIStatus", "LogLevel",
    "MetricType", "AlertLevel",
    "Pipeline", "Job", "LogEntry",
    "Metric", "Alert",
    "PipelineRunner", "LogAggregator",
    "MetricsCollector", "AlertManager",
    "HealthCheck", "ServiceDiscovery",
    "ConfigManager",
    "create_pipeline_runner", "create_log_aggregator",
    "create_metrics_collector", "create_alert_manager",
    "create_health_check", "create_service_discovery",
    "create_config_manager",
    "_register_devops", "_devops_names",
]
