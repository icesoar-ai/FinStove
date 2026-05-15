"""Report text analysis — extract metrics, audit opinion, risk factors from A股 年报/半年报/季报."""
import re
from pathlib import Path
from typing import Optional

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal

# Audit opinion patterns (ordered by severity — first match wins)
AUDIT_PATTERNS = [
    ("标准无保留意见", "audit_clean", "bullish", 0.2),
    ("无保留意见", "audit_clean", "bullish", 0.1),
    ("无法表示意见", "audit_disclaimer", "bearish", 1.0),
    ("否定意见", "audit_adverse", "bearish", 1.0),
    ("保留意见", "audit_qualified", "bearish", 0.7),
]

# Financial metrics to extract (label, regex pattern)
METRIC_PATTERNS = [
    ("营业收入", r"营业收入\s*[（(]?[元]?[）)]?\s*([\d,]+\.?\d*)\s*[亿万]?"),
    ("归母净利润", r"归属于(?:上市公司|母公司).*?净利润[^率].*?([\d,]+\.?\d*)\s*[亿万]?"),
    ("扣非净利润", r"扣除非经常性损益.*?净利润.*?([\d,]+\.?\d*)\s*[亿万]?"),
    ("基本每股收益", r"基本每股收益[（(]?[元／股/股]?[）)]?\s*([\d.]+\.?\d*)"),
    ("加权平均ROE", r"加权平均净资产收益率[（(]?%[）)]?\s*([\d.]+\.?\d*)"),
    ("经营现金流净额", r"经营活动.*?现金流量净额[^0-9]*?([\d,]+\.?\d*)\s*[亿万]?"),
]

# Risk-related keywords with weights
RISK_KEYWORDS_NEG = [
    "风险", "不确定性", "诉讼", "担保", "质押", "关联交易",
    "处罚", "罚款", "整改", "警告", "退市",
]
RISK_KEYWORDS_POS = [
    "无重大诉讼", "无违规担保", "内控有效", "合规",
]

OUTLOOK_POS = ["增长", "扩大", "研发", "转型", "升级", "创新", "拓展", "优化"]
OUTLOOK_NEG = ["下滑", "亏损", "缩减", "收缩", "困难", "挑战"]


def _find_latest_report(ticker_dir: str) -> Optional[Path]:
    """Find the most recent report MD file (any type: annual/semi-annual/quarterly)."""
    reports_dir = Path(f"data/stock/cn/{ticker_dir}/reports")
    if not reports_dir.exists():
        return None
    files = sorted(reports_dir.glob("*.md"))
    # Prefer non-summary, non-补充 (supplement) versions
    full = [f for f in files if "摘要" not in f.name and "补充" not in f.name]
    if full:
        return full[-1]
    main = [f for f in files if "补充" not in f.name]
    return main[-1] if main else (files[-1] if files else None)


def _parse_number(s: str) -> Optional[float]:
    """Parse a number string, handling commas and 亿/万 units."""
    if not s:
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _extract_audit(text: str) -> list[Signal]:
    """Extract audit opinion signals."""
    for pattern, name, direction, strength in AUDIT_PATTERNS:
        if pattern in text:
            return [Signal(name, direction, strength, f"审计意见: {pattern}")]
    return []


def _extract_metrics(text: str) -> dict[str, Optional[float]]:
    """Extract key financial metrics from report text using regex."""
    results = {}
    for label, pattern in METRIC_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            # Take the first match (usually the latest year)
            val = _parse_number(matches[0])
            results[label] = val
        else:
            results[label] = None
    return results


def _extract_risk_factors(text: str) -> list[Signal]:
    """Count risk-related keywords in the report."""
    neg_count = sum(text.count(k) for k in RISK_KEYWORDS_NEG)
    pos_count = sum(text.count(k) for k in RISK_KEYWORDS_POS)

    signals = []
    if neg_count > 50:
        signals.append(Signal("风险提示较多", "bearish", 0.3, f"风险关键词出现 {neg_count} 次"))
    else:
        signals.append(Signal("风险提示正常", "neutral", 0.1, f"风险关键词 {neg_count} 次"))

    if "重大诉讼" in text and "无重大诉讼" not in text:
        signals.append(Signal("存在重大诉讼", "bearish", 0.5, "报告披露重大诉讼"))

    return signals


def _extract_outlook(text: str) -> list[Signal]:
    """Extract management outlook signals."""
    pos_count = sum(text.count(k) for k in OUTLOOK_POS)
    neg_count = sum(text.count(k) for k in OUTLOOK_NEG)

    signals = []
    if pos_count > neg_count * 2:
        signals.append(Signal("管理层展望积极", "bullish", 0.2,
                              f"正面词 {pos_count} vs 负面词 {neg_count}"))
    elif neg_count > pos_count * 2:
        signals.append(Signal("管理层展望谨慎", "bearish", 0.2,
                              f"负面词 {neg_count} vs 正面词 {pos_count}"))
    return signals


class ReportTextAnalyzer(AbstractAnalyzer):
    """Analyze report MD text (annual/semi-annual/quarterly) for audit opinion, risks, and outlook.

    Complements fundamental analysis with qualitative signals from the
    management discussion and notes. Only works for CN stocks (reports
    downloaded via CNINFOProvider).
    """

    dimension = Dimension.FUNDAMENTAL

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        ticker_str = context.ticker.symbol if hasattr(context.ticker, 'symbol') else str(context.ticker)
        signals: list[Signal] = []
        metrics = {}
        warnings = []

        # Find report file
        report_path = _find_latest_report(ticker_str)
        if report_path is None:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.1,
                signals=[], summary="未找到报告MD文件",
                warnings=["请先运行 /fetch-stock <TICKER> reports 下载报告"],
            )

        try:
            text = report_path.read_text(encoding="utf-8")
        except Exception:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.1,
                signals=[], summary="报告文件读取失败",
            )

        # 1. Audit opinion
        signals.extend(_extract_audit(text))

        # 2. Financial metrics
        metrics = _extract_metrics(text)

        # 3. Risk factors
        signals.extend(_extract_risk_factors(text))

        # 4. Management outlook
        signals.extend(_extract_outlook(text))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="报告文本未提取到有效信号",
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.6, len(signals) / 5)

        # Determine if audit is clean
        audit_clean = any("audit_clean" in s.name for s in signals)
        if not audit_clean and any("audit" in s.name for s in signals):
            warnings.append("审计意见非标准无保留！")

        qual = "正面" if score > 0.2 else ("负面" if score < -0.2 else "中性")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"报告文本分析{qual}，审计{'清洁' if audit_clean else '需关注'}",
            details={"metrics": metrics, "report": str(report_path)},
            warnings=warnings,
        )
