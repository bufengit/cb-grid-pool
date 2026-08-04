# 可转债网格策略池 V1

一个不自动下单的可转债筛选工具：GitHub Actions 在每个交易日收盘后调用免费公开行情，计算候选/观察/正式/移除状态，并把最新快照写入 `data/latest.json`；GitHub Pages 只展示结果。

## 首次启用

1. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
2. 进入 **Actions → 更新可转债策略池 → Run workflow**，手动运行一次。
3. 等两项工作流均为绿色后，打开 Pages 地址。

## 策略安全原则

- 关键字段（评级、剩余规模、剩余期限、税后到期收益）缺失或无法核验时，标的只能停留在“数据待核验”，绝不会自动进入正式池。
- 强赎、到期、ST、信用风险等事件命中后直接移除；事件数据源失败也不会把已有标的误升为正式池。
- 首次满足硬门槛后，需要至少三份相邻交易日快照连续达标，下一交易日才会显示为正式池。
- 数据用于研究和筛选，不构成买卖建议。

## 数据源与限制

- 行情和转股溢价率：AkShare 聚合的公开数据。
- 公告风险：东方财富公告检索接口按债券代码扫描标题；这是辅助拦截，不能替代人工核对公司公告。
- 公开源对评级、剩余规模、剩余期限、税后 YTM 的覆盖并不稳定。因此 V1 的默认策略是宁可少入池，也不把字段缺失的债放进正式池。可在 `data/manual_overrides.json` 填入经核验的字段来补全。

## 本地运行

```bash
pip install -r requirements.txt
python scripts/update_pool.py
python -m http.server 8000
```
