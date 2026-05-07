"""CNINFO (巨潮资讯网) provider for annual report PDFs + Markdown conversion.

API: http://www.cninfo.com.cn/new/hisAnnouncement/query
PDF: http://static.cninfo.com.cn/{adjunctUrl}
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

import requests

from ..storage import ParquetStorage


class CNINFOProvider:
    BASE_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    PDF_BASE = "http://static.cninfo.com.cn"
    TIMEOUT = 30

    def __init__(self, storage: Optional[ParquetStorage] = None):
        self._storage = storage or ParquetStorage()

    def _build_stock_id(self, symbol: str) -> str:
        padded = symbol.zfill(7)
        if symbol.startswith(("0", "3")):
            return f"{symbol},gssz{padded}"
        return f"{symbol},gssh{padded}"

    def _fetch_page(self, stock_id: str, page: int, page_size: int = 50) -> dict:
        data = {
            "pageNum": page, "pageSize": page_size,
            "column": "szse", "tabName": "fulltext",
            "plate": "", "stock": stock_id,
            "searchkey": "", "secid": "",
            "category": "category_ndbg_szsh",
            "trade": "", "seDate": "",
            "sortName": "", "sortType": "",
            "isHLtitle": "true",
        }
        r = requests.post(self.BASE_URL, data=data, timeout=self.TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _parse_time(self, t) -> str:
        if isinstance(t, (int, float)):
            from datetime import datetime
            return datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d")
        if isinstance(t, str):
            return t[:10] if len(t) >= 10 else t
        return ""

    # ---- Listing ----

    def list_reports(self, symbol: str) -> list[dict]:
        """List all annual reports (年报 + 年报摘要) for a stock."""
        stock_id = self._build_stock_id(symbol)
        resp = self._fetch_page(stock_id, 1, 50)
        announcements = resp.get("announcements") or []
        results = []

        for a in announcements:
            title = a.get("announcementTitle", "")
            adjunct = a.get("adjunctUrl", "")
            if not adjunct:
                continue
            if "年度报告" not in title:
                continue

            year_match = re.search(r"(\d{4})", title)
            year = int(year_match.group(1)) if year_match else 0
            is_summary = "摘要" in title
            kind = "summary" if is_summary else "full"
            results.append({
                "title": title,
                "year": year,
                "kind": kind,
                "pdf_url": f"{self.PDF_BASE}/{adjunct}",
                "announcement_id": a.get("announcementId", ""),
                "publish_date": self._parse_time(a.get("announcementTime", "")),
            })

        return sorted(results, key=lambda x: (x["year"], x["kind"]), reverse=True)

    # ---- Download ----

    def _download_file(self, url: str, dest: Path) -> bool:
        if dest.exists() and dest.stat().st_size > 0:
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            r = requests.get(url, headers=headers, timeout=120, stream=True)
            r.raise_for_status()
            if not r.content[:4] == b"%PDF":
                return False
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception:
            return False

    def _convert_to_markdown(self, pdf_path: Path, md_path: Path) -> bool:
        """Convert PDF to Markdown using markitdown. Returns True on success."""
        if md_path.exists() and md_path.stat().st_size > 0:
            return True
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(str(pdf_path))
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(result.text_content, encoding="utf-8")
            return True
        except Exception:
            return False

    # ---- Public API ----

    def download_reports(self, symbol: str, years: Optional[list[int]] = None) -> list[dict]:
        """Download annual reports (full + summary) for a stock.

        Filenames use the original CNINFO announcement title directly.
        """
        from src.utils.ticker import stock_dir

        reports = self.list_reports(symbol)

        if years:
            reports = [r for r in reports if r["year"] in years]

        dir_name = stock_dir(symbol)
        results = []

        for r in reports:
            # Use original title as filename (sanitize only invalid chars)
            safe_title = r["title"].replace("/", "_").replace(":", "_").replace("?", "")

            # PDF
            pdf_dest = self._storage._path("stock", "cn", dir_name, f"reports/{safe_title}")
            pdf_dest = Path(str(pdf_dest).replace(".parquet", ".pdf"))
            pdf_ok = self._download_file(r["pdf_url"], pdf_dest)

            # Markdown
            md_ok = False
            if pdf_ok:
                md_dest = Path(str(pdf_dest).replace(".pdf", ".md"))
                md_ok = self._convert_to_markdown(pdf_dest, md_dest)

            r["downloaded"] = pdf_ok
            r["pdf_path"] = str(pdf_dest) if pdf_ok else ""
            r["md_path"] = str(pdf_dest).replace(".pdf", ".md") if md_ok else ""
            results.append(r)

            if pdf_ok:
                time.sleep(0.5)

        return results