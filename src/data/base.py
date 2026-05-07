from enum import Enum, auto


class Market(Enum):
    CN = "cn"
    HK = "hk"
    US = "us"
    JP = "jp"
    UK = "uk"
    DE = "de"
    FR = "fr"


class AssetType(Enum):
    STOCK = auto()
    INDEX = auto()
    BOND = auto()
    FOREX = auto()
    COMMODITY = auto()
    CRYPTO = auto()
    MACRO = auto()
    NEWS = auto()


class Dimension(Enum):
    MACRO = "macro"
    CAPITAL_FLOW = "capital_flow"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    RISK = "risk"
    BENCHMARK = "benchmark"
    SCENARIO = "scenario"
    SENTIMENT = "sentiment"
    POLICY = "policy"
    CORRELATION = "correlation"
