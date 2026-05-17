from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ColorScheme:
    """涨跌颜色方案 — 各组件通过语义取值，不直接写颜色值."""
    up: str         # 涨 / 看多 / 趋势向上 / 利差正常 / 资金流入
    down: str       # 跌 / 看空 / 趋势向下 / 利差倒挂 / 资金流出
    neutral: str = "dim"
    warning: str = "yellow"

    @classmethod
    def cn(cls) -> ColorScheme:
        """中国方案: 红涨绿跌."""
        return cls(up="red", down="green")

    @classmethod
    def us(cls) -> ColorScheme:
        """国际方案: 绿涨红跌."""
        return cls(up="green", down="red")

    @classmethod
    def get(cls, scheme: str, market: str = "") -> ColorScheme:
        """根据配置和市场取色.

        scheme: "cn" | "us" | "auto"
        market: "cn" | "us" | ... (仅 scheme="auto" 时生效)
        """
        if scheme == "auto":
            return cls.cn() if market == "cn" else cls.us()
        return cls.cn() if scheme == "cn" else cls.us()

    def chg_color(self, val: float) -> str:
        """涨跌幅颜色: 正→up, 负→down, 0→neutral."""
        return self.up if val > 0 else (self.down if val < 0 else self.neutral)

    def trend_color(self, trend: str) -> str:
        """趋势箭头颜色: ↑→up, ↓→down."""
        return self.up if trend == "↑" else self.down

    def score_color(self, score: float, threshold: float = 0.2) -> str:
        """评分颜色: >threshold→up, <-threshold→down, 否则→warning."""
        return self.up if score > threshold else (self.down if score < -threshold else self.warning)


def load_scheme(market: str = "") -> ColorScheme:
    """从 config/settings.yaml 加载配色方案."""
    settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    with open(settings_path) as f:
        cfg = yaml.safe_load(f) or {}
    scheme = cfg.get("output", {}).get("color_scheme", "cn")
    return ColorScheme.get(scheme, market=market)
