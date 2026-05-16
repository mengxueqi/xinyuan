# Xinyuan Monitor Reference

这份文档用于说明当前项目的核心思路、数据流、模块职责，以及后续扩展时应该遵循的原则。

## 1. 项目目标

本项目是一个面向生物制造公司的本地监控系统，核心目标不是简单聚合网页，而是形成一条稳定的数据链路：

1. 抓取原始事件和页面内容
2. 建立历史事件库
3. 识别变化
4. 对事件和变化做分析、评价、打分
5. 从已处理事件库中提取重点事件
6. 用 Dashboard 和 Report 分别承载不同视角

## 2. 当前主数据流

当前项目已经重构为下面这条主线：

`原始抓取 -> events -> change_logs -> processed_events / insight_items -> focus events`

更具体地说：

- `events`
  - 原始事件库
  - 保存所有结构化事件候选
- `change_logs`
  - 变化层
  - 保存“历史上首次出现的事件”以及页面/招聘变化
- `processed_events`
  - 已处理事件库
  - 所有事件候选都会在这里被摘要、评价、打分
  - 首次入库但不是变化层重点的事件，也会进这里
- `insight_items`
  - 变化分析层
  - 只服务 `Dashboard -> Change Analysis`
- `focus events`
  - 从 `processed_events` 中提取
  - 用于 `Report`

## 3. 页面职责

### Dashboard

Dashboard 只展示两层：

- `New Events`
  - 来自 `change_logs`
  - 代表历史上新增的变化
- `Change Analysis`
  - 来自 `insight_items`
  - 代表对变化的解释、判断和评分

Dashboard 不再展示 Focus 事件。

### Report

Report 只展示：

- `Focus Events`
  - 来自 `processed_events`
  - 是近期重点事件视图

### Event Query

Event Query 直接查询：

- `events`

它是原始事件库检索页，不依赖变化层。

## 4. 三种文本字段的明确语义

为了避免“看起来像分析，其实只是打分依据”这种混乱，当前项目统一采用下面的定义。

### `summary`

回答：

- `发生了什么`

要求：

- 用人话描述
- 简短
- 偏事实

例如：

- `川宁生物 出现新的performance事件：川宁生物:2026年一季度报告`
- `某公司 的官网页面发生更新：新闻动态页`

### `reason`

回答：

- `为什么值得关注`

要求：

- 是业务判断
- 不是机械列出命中词

例如：

- `这属于业绩披露或经营表现相关信息，适合结合后续经营动态持续观察。`
- `这可能反映产能、项目建设或制造能力推进，是产业化的重要信号。`

### `score_basis`

回答：

- `为什么系统打了这个分`

要求：

- 放在 metadata 中
- 默认不在主 UI 正文里展示

它适合调试、复盘规则，不适合直接替代业务判断。

## 5. New Events 的逻辑

当前 `New Events` 不是“当前批次和上一批次比”，而是：

- 当前事件
- 对比历史事件库
- 如果历史中从未出现过，且满足发布时间窗口与来源规则
- 才进入 `change_logs`

当前事件变化窗口：

- `60 天`

这样做的目的：

- 避免因为上一批漏抓导致变化判断失真
- 避免老事件第一次抓到就被误判成当天新增

## 6. Focus Events 的逻辑

Focus 事件不是直接从变化层取，而是从 `processed_events` 提取。

当前筛选规则：

- 时间窗口：`60 天`
- 重点类型：
  - `product`
  - `financing`
  - `capacity`
  - `ip`
  - `performance`
- 数量上限：最多 `20` 条
- 每家公司最多 `6` 条
- 保留多样性
- 在满足多样性前提下，更优先最近发生的事件

排序基础：

- `processed_events.importance_score`
- Focus 类型权重
- 来源偏好
- 时间新近程度

## 7. 评分体系

当前项目已经统一为一套评分家族：

- 事件评分：用于 `processed_events`
- 变化评分：用于 `insight_items`

二者不是完全同一条公式，但语义已经统一：

- 分数越高，代表越值得关注
- `low / medium / high` 只是标签
- 不再出现“一个给用户看，一个只给机器看”的双重体系混乱

当前重点加权类型：

- `product`
- `financing`
- `capacity`
- `ip`
- `performance`

其中业绩类关键词现在已经覆盖：

- `业绩`
- `业绩快报`
- `业绩预告`
- `业绩说明会`
- `年报`
- `半年报`
- `一季度报告`
- `三季度报告`

## 8. 当前主要模块职责

### `collectors/`

负责采集：

- 官网
- 新闻页
- RSS
- 招聘页
- 东方财富公告/财务页

### `processors/`

负责：

- 标准化
- 去重
- 公司匹配
- 事件分类

### `detectors/`

负责：

- 新事件检测
- 页面变化检测
- 招聘变化检测

### `insights/`

负责：

- 摘要
- 原因判断
- 评分
- 已处理事件层的构造

### `business_db/repository.py`

负责：

- SQLite 表结构
- 批次同步
- UI 和 Report 读取接口

### `ui_app.py`

负责：

- Report
- Dashboard
- Event Query

## 9. 关键数据表

当前业务库核心表：

- `companies`
- `sources`
- `events`
- `change_logs`
- `processed_events`
- `insight_items`
- `report_runs`
- `task_runs`

建议记忆方式：

- `events`：抓到过什么
- `change_logs`：什么是新的变化
- `processed_events`：所有事件怎么被分析和评分
- `insight_items`：变化为什么值得关注

## 10. 当前推荐的维护原则

1. 不要把 `reason` 再退回成“命中了哪些词”
2. 不要让 `Dashboard` 和 `Report` 读同一层数据
3. 不要让 `Focus Events` 直接从 `events` 取
4. 新增规则时，优先改：
   - `processors/classify.py`
   - `insights/scoring.py`
   - `insights/reasoning.py`
   - `utils/focus_events.py`
5. 调规则后，记得重建：
   - `build_insights`
   - `sync_business_db`

## 11. 一句话总结

当前项目的正确心智模型是：

- `events` 是原始事件库
- `change_logs` 是变化层
- `processed_events` 是统一分析评分后的事件层
- `insight_items` 是变化解释层
- `Dashboard` 看变化
- `Report` 看重点事件
