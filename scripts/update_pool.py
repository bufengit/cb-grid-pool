"""可转债网格策略池 V1：免费公开数据采集、风险标签和安全分池。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY = DATA / "history"
LATEST = DATA / "latest.json"
OVERRIDES = DATA / "manual_overrides.json"

RISK_PATTERN = re.compile(r"强制?赎回|提前赎回|到期赎回|最后交易日|终止上市|暂停上市|违约|评级下调|信用风险|ST")

def clean_number(value: Any) -> float | None:
    if value is None or pd.isna(value): return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "--", "None", "nan"}: return None
    try: return float(text)
    except ValueError: return None

def get(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] is not None and not pd.isna(row[name]): return row[name]
    return None

def load_overrides() -> dict[str, dict[str, Any]]:
    try: return json.loads(OVERRIDES.read_text(encoding="utf-8")).get("bonds", {})
    except (OSError, json.JSONDecodeError): return {}

def fetch_market() -> list[dict[str, Any]]:
    """读取可转债比价表，并合并基础资料。

    这两个接口都是一次性表格请求。旧版逐只扫描公告（数百次网络请求）会让
    首次更新非常慢，常常在本地被用户中断，最终页面一直保持空数据。
    """
    comparison = ak.bond_cov_comparison()
    basics = ak.bond_zh_cov()
    basic_by_code = {
        str(get(row, "债券代码") or "").zfill(6): row
        for row in basics.to_dict(orient="records")
    }
    rows: list[dict[str, Any]] = []
    for raw in comparison.to_dict(orient="records"):
        code = str(get(raw, "转债代码", "债券代码", "代码") or "").zfill(6)
        price = clean_number(get(raw, "转债最新价", "债券最新价", "最新价"))
        if not code or price is None:
            continue
        basic = basic_by_code.get(code, {})
        rows.append({
            "code": code,
            "name": str(get(raw, "转债名称", "债券简称", "名称") or code),
            "stock": str(get(raw, "正股名称", "正股简称") or get(basic, "正股简称") or "—"),
            "price": price,
            "change": clean_number(get(raw, "转债涨跌幅", "债券涨跌幅", "涨跌幅")),
            "premium": clean_number(get(raw, "转股溢价率")),
            "redeem_price": clean_number(get(raw, "到期赎回价")),
            "rating": get(basic, "信用评级"),
            # 发行规模不等于剩余规模，不能替代正式池的 balance 字段。
            "issue_size": clean_number(get(basic, "发行规模")),
            "listed_at": str(get(raw, "上市日期") or get(basic, "上市时间") or ""),
            "events": [],
        })
    return rows

def prior_snapshots() -> list[dict[str, Any]]:
    files = sorted(HISTORY.glob("*.json"))[-60:]
    result = []
    for file in files:
        try: result.append(json.loads(file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError): pass
    return result

def field_complete(bond: dict[str, Any]) -> bool:
    required = ["balance", "years", "rating", "ytm", "turnover", "premium"]
    return all(bond.get(field) not in (None, "", "—") for field in required)

def rating_ok(value: Any) -> bool:
    # AA-、AA、AA+、AAA 通过；AA- 以下和无法识别都不通过
    return str(value).upper().replace(" ", "") in {"AA-", "AA", "AA+", "AAA"}

def classify(bond: dict[str, Any], previous: list[dict[str, Any]]) -> dict[str, Any]:
    events = bond.get("events", [])
    immediate = [e for e in events if RISK_PATTERN.search(e)]
    complete = field_complete(bond)
    basics = complete and 112 <= bond["price"] <= 125 and bond["balance"] >= 2 and 1.5 <= bond["years"] <= 4.5 and rating_ok(bond["rating"]) and bond["premium"] <= 130 and bond["ytm"] >= -6 and bond["turnover"] >= 3000
    # 以每日快照里的价格推近60日“至少1元”的有效波动；首次或缺历史不作通过处理
    prices = [s.get("prices", {}).get(bond["code"]) for s in previous]
    prices = [p for p in prices if isinstance(p, (int, float))]
    grid_days = sum(1 for a, b in zip(prices, prices[1:]) if abs(b - a) >= 1)
    bond["grid_days"] = grid_days
    qualifies = basics and grid_days >= 20 and not immediate
    streak = 1
    for snap in reversed(previous):
        found = next((x for x in snap.get("bonds", []) if x.get("code") == bond["code"]), None)
        if found and found.get("qualifies") is True: streak += 1
        else: break
    bond["qualifies"] = qualifies
    bond["streak"] = streak if qualifies else 0
    failures = []
    if not complete: failures.append("关键字段待核验")
    if complete:
        checks = [(112 <= bond["price"] <= 125, "价格不在112–125元"), (bond["balance"] >= 2, "剩余规模低于2亿元"), (1.5 <= bond["years"] <= 4.5, "剩余期限不在1.5–4.5年"), (rating_ok(bond["rating"]), "评级低于AA-"), (bond["premium"] <= 130, "转股溢价率高于130%"), (bond["ytm"] >= -6, "税后到期收益低于-6%"), (bond["turnover"] >= 3000, "日均成交额低于3000万元")]
        failures.extend(label for ok, label in checks if not ok)
    if grid_days < 20: failures.append(f"60日有效波动仅{grid_days}天")
    if immediate:
        bond.update(status="removed", status_label="已移除", reason="；".join(immediate[:2]), risk_level="high")
    elif qualifies and streak >= 4:
        bond.update(status="official", status_label="正式池", reason="所有硬门槛连续满足3个交易日，今日转正式池", risk_level="low")
    elif qualifies:
        bond.update(status="candidate", status_label="候选确认中", reason=f"硬门槛达标，已连续{streak}/3日确认", risk_level="medium")
    else:
        bond.update(status="watch", status_label="观察 / 待核验", reason="；".join(failures[:3]) or "等待数据更新", risk_level="medium")
    return bond

def main() -> None:
    DATA.mkdir(exist_ok=True); HISTORY.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    overrides = load_overrides(); previous = prior_snapshots()
    try:
        raw_bonds = fetch_market(); source_status = "公开行情已更新"; source_note = "已加载可转债实时行情。剩余规模、期限、税后YTM等未核验字段会停留在观察区。"
    except Exception as exc:  # 工作流必须保留旧数据而非清空策略池
        old = json.loads(LATEST.read_text(encoding="utf-8")) if LATEST.exists() else {"bonds": []}
        old.update({"source_status": "本次更新失败，保留上一份结果", "source_note": str(exc)[:160]})
        LATEST.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    bonds = []
    for bond in raw_bonds:
        bond.update(overrides.get(bond["code"], {}))
        bonds.append(classify(bond, previous))
    bonds.sort(key=lambda x: (x["status"] != "official", -(x.get("price") or 0)))
    payload = {"generated_at": now.isoformat(), "source_status": source_status, "source_note": source_note,
               "summary": {"total": len(bonds), "official": sum(x["status"] == "official" for x in bonds), "candidate": sum(x["status"] == "candidate" for x in bonds), "watch": sum(x["status"] == "watch" for x in bonds), "removed": sum(x["status"] == "removed" for x in bonds)}, "bonds": bonds}
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot = {"date": now.date().isoformat(), "prices": {b["code"]: b["price"] for b in bonds}, "bonds": [{"code": b["code"], "qualifies": b["qualifies"]} for b in bonds]}
    (HISTORY / f"{now.date().isoformat()}.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__": main()
