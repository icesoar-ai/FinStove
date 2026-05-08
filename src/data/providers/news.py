"""News data provider — AKShare stock news + CCTV macro news."""
from datetime import date, datetime, timedelta
from typing import Optional
import re

import pandas as pd

from ..cache import DataCache
from ..models import NewsItem


class NewsProvider:
    """Fetch news from AKShare (Eastmoney + CCTV)."""

    def __init__(self, cache: Optional[DataCache] = None):
        self._cache = cache
        import akshare as ak
        self._ak = ak

    def get_stock_news(self, symbol: str, days: int = 7) -> list[NewsItem]:
        """Individual stock news from Eastmoney."""
        try:
            df = self._ak.stock_news_em(symbol=symbol)
        except Exception:
            return []

        if df is None or df.empty:
            return []

        cutoff = datetime.now() - timedelta(days=days)
        items = []
        for _, r in df.iterrows():
            try:
                pub_str = str(r.get("发布时间", ""))
                pub_time = pd.to_datetime(pub_str).to_pydatetime()
            except Exception:
                pub_time = datetime.now()

            if pub_time < cutoff:
                continue

            url = str(r.get("新闻链接", "")) if pd.notna(r.get("新闻链接")) else ""
            # Keep only the numeric ID from the URL
            if url:
                m = re.search(r'(news/\d+)', url)
                if m:
                    url = f"https://finance.eastmoney.com/a/{m.group(1)}.html"

            items.append(NewsItem(
                date=pub_time,
                title=str(r.get("新闻标题", "")),
                source=str(r.get("文章来源", "东方财富")),
                url=url,
                summary=str(r.get("新闻内容", ""))[:500] if pd.notna(r.get("新闻内容")) else "",
            ))

        return items

    def get_macro_news(self) -> list[NewsItem]:
        """Macro/policy news from CCTV (新闻联播)."""
        items = []
        for d_offset in range(3):
            dt = (date.today() - timedelta(days=d_offset)).strftime("%Y%m%d")
            try:
                df = self._ak.news_cctv(date=dt)
                if df is not None and not df.empty:
                    for _, r in df.iterrows():
                        items.append(NewsItem(
                            date=datetime.fromisoformat(str(r.get("date", dt))),
                            title=str(r.get("title", "")),
                            source="CCTV 新闻联播",
                            url="",
                            summary=str(r.get("content", ""))[:500],
                        ))
            except Exception:
                continue

        return items

    def get_all_news(self, symbol: str, days: int = 7) -> list[NewsItem]:
        """Stock news + macro news combined."""
        stock = self.get_stock_news(symbol, days=days)
        macro = self.get_macro_news()
        return stock + macro
