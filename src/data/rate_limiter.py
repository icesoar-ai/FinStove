"""数据驱动的访问限速器。

所有 provider 差异化配置来自 providers.yaml 的 `rate_limit` 段。
代码不写死任何 provider 特定逻辑，纯根据配置数据驱动。
"""
from __future__ import annotations

import random
import time
import threading
from pathlib import Path
from typing import Optional

import yaml


class RateLimiter:
    """每个 Provider 独立的访问节奏控制 + 退避重试 + 冷却机制。

    使用方式:
        limiter = RateLimiter.from_yaml("config/providers.yaml")
        for attempt in limiter.attempts("akshare"):
            data = provider.fetch()
            if data is not None:
                limiter.report("akshare", success=True)
                break
            limiter.report("akshare", success=False)
    """

    def __init__(self, config: dict):
        self._cfg = config.get("rate_limit", {})
        self._default = self._cfg.get("default", {})
        self._lock = threading.Lock()
        self._state: dict[str, dict] = {}  # provider → {last_call_ts, failures, cooldown_until}

    @classmethod
    def from_yaml(cls, path: str) -> "RateLimiter":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(raw)

    # ── 公共接口 ──────────────────────────────────────

    def attempts(self, provider: str) -> "AttemptIterator":
        """返回一个迭代器，每次迭代前自动等待 + 退避。

        for attempt in limiter.attempts("akshare"):
            data = do_request()
            if data is not None:
                attempt.success()
                return data
            attempt.failure()
        raise TimeoutError("all retries exhausted")
        """
        return AttemptIterator(self, provider)

    def acquire(self, provider: str):
        """阻塞直到允许发起下一次请求。不做请求，只做等待。"""
        with self._lock:
            cfg = self._provider_cfg(provider)
            state = self._ensure_state(provider)

            # 1. 检查冷却
            now = time.monotonic()
            cooldown_until = state.get("cooldown_until", 0)
            if now < cooldown_until:
                remaining = cooldown_until - now
                raise RateLimitError(provider, f"冷却中，剩余 {remaining:.0f}s")

            # 2. 距上次调用的间隔
            elapsed_ms = (now - state.get("last_call_ts", 0)) * 1000
            min_ms = cfg.get("min_interval_ms", 1000)
            jitter_pct = cfg.get("jitter_pct", 0) / 100.0
            target_ms = min_ms + random.uniform(-jitter_pct, jitter_pct) * min_ms

            if elapsed_ms < target_ms:
                wait_ms = target_ms - elapsed_ms
                state["last_call_ts"] = now + wait_ms / 1000
                time.sleep(wait_ms / 1000)
            else:
                state["last_call_ts"] = now

    def report(self, provider: str, success: bool):
        """上报请求结果，更新失败计数和冷却状态。"""
        with self._lock:
            cfg = self._provider_cfg(provider)
            state = self._ensure_state(provider)

            if success:
                state["failures"] = 0
            else:
                state["failures"] = state.get("failures", 0) + 1
                threshold = cfg.get("cooldown_failures", 5)
                if state["failures"] >= threshold:
                    cooldown_ms = cfg.get("cooldown_ms", 30000)
                    state["cooldown_until"] = time.monotonic() + cooldown_ms / 1000

    def backoff_delay(self, provider: str, attempt: int) -> float:
        """计算第 N 次重试的退避等待秒数（含抖动）。"""
        cfg = self._provider_cfg(provider)
        strategy = cfg.get("backoff", "linear")
        base = cfg.get("backoff_base_ms", 2000) / 1000.0
        jitter_pct = cfg.get("jitter_pct", 0) / 100.0

        if strategy == "exponential":
            delay = base * (2 ** (attempt - 1))
        elif strategy == "fixed":
            delay = base
        else:  # linear
            delay = base * attempt

        delay += random.uniform(-jitter_pct, jitter_pct) * delay
        return max(0, delay)

    def max_retries(self, provider: str) -> int:
        return self._provider_cfg(provider).get("max_retries", 1)

    # ── 内部 ────────────────────────────────────────

    def _provider_cfg(self, provider: str) -> dict:
        return self._cfg.get(provider, self._default)

    def _ensure_state(self, provider: str) -> dict:
        if provider not in self._state:
            self._state[provider] = {"last_call_ts": 0, "failures": 0, "cooldown_until": 0}
        return self._state[provider]


class AttemptIterator:
    """重试迭代器 — 封装 acquire + backoff 逻辑。"""

    def __init__(self, limiter: RateLimiter, provider: str):
        self._limiter = limiter
        self._provider = provider
        self._attempt = 0
        self._max = limiter.max_retries(provider)

    def __iter__(self):
        return self

    def __next__(self):
        if self._attempt >= self._max:
            raise StopIteration
        self._attempt += 1

        if self._attempt > 1:
            delay = self._limiter.backoff_delay(self._provider, self._attempt - 1)
            if delay > 0:
                time.sleep(delay)
        try:
            self._limiter.acquire(self._provider)
        except RateLimitError:
            raise StopIteration  # in cooldown, give up
        return self

    def success(self):
        self._limiter.report(self._provider, True)

    def failure(self):
        self._limiter.report(self._provider, False)


class RateLimitError(Exception):
    def __init__(self, provider: str, detail: str):
        super().__init__(f"[{provider}] {detail}")
        self.provider = provider
