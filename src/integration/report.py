from __future__ import annotations

from .aggregator import AggregatedJudgment

DISCLAIMER = "> 本报告基于公开免费数据源生成，仅供参考，不构成投资建议。"

TIER_LABELS = {
    "STRONG_BUY": "强烈买入",
    "BUY": "买入",
    "HOLD": "持有/观望",
    "SELL": "卖出",
    "STRONG_SELL": "强烈卖出",
}


class ReportBuilder:
    def build(self, judgment: AggregatedJudgment, format: str = "standard") -> str:
        if format == "brief":
            return self._build_brief(judgment)
        elif format == "full":
            return self._build_full(judgment)
        return self._build_standard(judgment)

    def _build_brief(self, j: AggregatedJudgment) -> str:
        lines = [
            f"# {j.ticker} 分析简报",
            "",
            f"**综合评分**: {j.composite_score:+.1f} → {TIER_LABELS.get(j.tier, j.tier)}",
            f"**趋势**: {j.trend_direction} | **风险**: {j.risk_level} | **vs基准**: {j.benchmark_edge}",
            "",
            DISCLAIMER,
        ]
        return "\n".join(lines)

    def _build_standard(self, j: AggregatedJudgment) -> str:
        lines = [
            f"# {j.ticker} 多维分析报告",
            "",
            f"## 综合判断",
            f"**综合评分**: {j.composite_score:+.1f} → **{TIER_LABELS.get(j.tier, j.tier)}**",
            "",
            f"| 维度 | 评分 |",
            f"|------|------|",
        ]
        for dim, score in j.dimension_scores.items():
            lines.append(f"| {dim} | {score:+.1f} |")

        lines.extend([
            "",
            f"**趋势判断**: {j.trend_direction}",
            f"**风险等级**: {j.risk_level}",
            f"**基准对比**: {j.benchmark_edge}",
            "",
            "## 各维度摘要",
            "",
        ])
        for sl in j.summary_lines:
            lines.append(f"- {sl}")

        if j.conflicts:
            lines.append("")
            lines.append("## 矛盾信号")
            for c in j.conflicts:
                lines.append(f"- ⚠ {c}")

        if j.intrinsic_value_range[0]:
            lines.extend([
                "",
                "## 估值区间",
                f"合理估值区间: **{j.intrinsic_value_range[0]:.2f} ~ {j.intrinsic_value_range[1]:.2f}**",
            ])

        lines.extend(["", DISCLAIMER])
        return "\n".join(lines)

    def _build_full(self, j: AggregatedJudgment) -> str:
        lines = [self._build_standard(j)]
        lines.append("")
        lines.append("## 情景分析")
        for k, v in j.scenarios.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
