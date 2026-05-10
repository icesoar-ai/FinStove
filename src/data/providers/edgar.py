"""SEC EDGAR provider — 美股年报 (10-K) 查询和下载.

Uses SEC EDGAR public API, no registration required.
CIK-to-ticker mapping from SEC company_tickers.json.
"""
from datetime import date
from pathlib import Path
from typing import Optional
import time

import requests


class SECEDGARProvider:
    """Provider for SEC EDGAR filings (10-K annual reports)."""

    BASE = "https://data.sec.gov/submissions"
    ARCHIVE = "https://www.sec.gov/Archives/edgar/data"
    HEADERS = {"User-Agent": "stocks-analysis/1.0 (contact@example.com)"}
    TIMEOUT = 15

    def __init__(self):
        self._cik_cache: dict[str, str] = {}

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

    def list_10k(self, ticker: str) -> list[dict]:
        """List recent 10-K (annual report) filings for a ticker.

        Returns list of dicts with keys: form, filing_date, report_date, accession, url.
        """
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
                if forms[i] == "10-K":
                    acc = accessions[i].replace("-", "")
                    results.append({
                        "form": forms[i],
                        "filing_date": dates[i],
                        "report_date": reports[i] or "",
                        "accession": accessions[i],
                        "description": descriptions[i] if i < len(descriptions) else "",
                        "url": f"{self.ARCHIVE}/{cik.lstrip('0')}/{acc}/{docs[i]}",
                    })
            return results
        except Exception:
            return []

    def download_10k(self, ticker: str, data_dir: str = "data/stock") -> list[dict]:
        """Download 10-K filing text for a ticker.

        Saves to data_dir/{market}/{symbol}/reports/{filename}.txt
        """
        results = self.list_10k(ticker)
        ticker_dir = Path(data_dir) / "us" / ticker / "reports"
        ticker_dir.mkdir(parents=True, exist_ok=True)

        for r in results:
            filename = f"{r['report_date'][:4]}_10K_{ticker}.txt"
            dest = ticker_dir / filename
            if dest.exists() and dest.stat().st_size > 0:
                r["downloaded"] = True
                r["path"] = str(dest)
                continue

            try:
                resp = requests.get(r["url"], headers=self.HEADERS, timeout=60, stream=True)
                resp.raise_for_status()
                dest.write_text(resp.text[:500000], encoding="utf-8")  # Cap at 500KB
                r["downloaded"] = True
                r["path"] = str(dest)
                time.sleep(0.2)  # SEC rate limit: 10 req/sec
            except Exception:
                r["downloaded"] = False

        return results
