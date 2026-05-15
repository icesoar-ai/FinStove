"""SEC EDGAR provider — 美股 filings (10-K/10-Q) 查询和下载.

Uses SEC EDGAR public API, no registration required.
CIK-to-ticker mapping from SEC company_tickers.json.
"""
from pathlib import Path
from typing import Optional
import time

import requests


class SECEDGARProvider:
    """Provider for SEC EDGAR filings (10-K annual, 10-Q quarterly)."""

    BASE = "https://data.sec.gov/submissions"
    ARCHIVE = "https://www.sec.gov/Archives/edgar/data"
    HEADERS = {"User-Agent": "stocks-analysis/1.0 (contact@example.com)"}
    TIMEOUT = 15
    FORM_TYPE_MAP = {
        "annual":    "10-K",
        "quarterly": "10-Q",
    }
    # Reverse lookup: form code → report_type key
    _FORM_TO_REPORT = {v: k for k, v in FORM_TYPE_MAP.items()}

    def __init__(self, data_dir: str = "data/stock"):
        self._cik_cache: dict[str, str] = {}
        self._data_dir = data_dir

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Resolve ticker to CIK using SEC's company_tickers.json."""
        ticker = ticker.upper()
        if ticker in self._cik_cache:
            return self._cik_cache[ticker]

        try:
            r = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=self.HEADERS, timeout=self.TIMEOUT
            )
            r.raise_for_status()
            for v in r.json().values():
                if v["ticker"] == ticker:
                    cik = str(v["cik_str"]).zfill(10)
                    self._cik_cache[ticker] = cik
                    return cik
        except Exception:
            pass
        return None

    def list_filings(self, ticker: str,
                     form_types: Optional[list[str]] = None,
                     since_year: Optional[int] = None) -> list[dict]:
        """List SEC filings for a ticker.

        Args:
            ticker: Stock ticker symbol
            form_types: List of form types, e.g. ["10-K", "10-Q"]. Default to both.
            since_year: Filter filings with report_date earlier than this year.
        """
        if form_types is None:
            form_types = ["10-K", "10-Q"]

        cik = self._get_cik(ticker)
        if not cik:
            return []

        try:
            url = f"{self.BASE}/CIK{cik}.json"
            r = requests.get(url, headers=self.HEADERS, timeout=self.TIMEOUT)
            r.raise_for_status()
            data = r.json()

            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            reports = filings.get("reportDate", [])
            docs = filings.get("primaryDocument", [])
            accessions = filings.get("accessionNumber", [])
            descriptions = filings.get("primaryDocDescription", [])

            results = []
            for i in range(len(forms)):
                if forms[i] not in form_types:
                    continue

                report_date = reports[i] or ""
                year = int(report_date[:4]) if report_date and len(report_date) >= 4 else 0
                if since_year is not None and year < since_year:
                    continue

                acc = accessions[i].replace("-", "")
                rtype = self._FORM_TO_REPORT.get(forms[i], "annual")

                results.append({
                    "form": forms[i],
                    "report_type": rtype,
                    "filing_date": dates[i],
                    "report_date": report_date,
                    "accession": accessions[i],
                    "description": descriptions[i] if i < len(descriptions) else "",
                    "url": f"{self.ARCHIVE}/{cik.lstrip('0')}/{acc}/{docs[i]}",
                })
            return results
        except Exception:
            return []

    def download_filings(self, ticker: str,
                         since_year: Optional[int] = None,
                         form_types: Optional[list[str]] = None) -> list[dict]:
        """Download SEC filings (10-K and/or 10-Q) for a ticker.

        Saves to data_dir/us/{ticker}/reports/{filename}.txt
        """
        results = self.list_filings(ticker, form_types=form_types, since_year=since_year)
        ticker_dir = Path(self._data_dir) / "us" / ticker / "reports"
        ticker_dir.mkdir(parents=True, exist_ok=True)

        for r in results:
            form = r["form"]
            report_date = r["report_date"] or ""
            # Use report_date YYYYMMDD to distinguish multiple filings per year (e.g. Q1/Q2/Q3 10-Q)
            date_prefix = report_date.replace("-", "") if report_date else "unknown"
            filename = f"{date_prefix}_{form}_{ticker}.txt"
            dest = ticker_dir / filename
            if dest.exists() and dest.stat().st_size > 0:
                r["downloaded"] = True
                r["path"] = str(dest)
                continue

            try:
                resp = requests.get(r["url"], headers=self.HEADERS, timeout=60, stream=True)
                resp.raise_for_status()
                dest.write_text(resp.text[:500000], encoding="utf-8")
                r["downloaded"] = True
                r["path"] = str(dest)
                time.sleep(0.2)
            except Exception:
                r["downloaded"] = False

        return results
