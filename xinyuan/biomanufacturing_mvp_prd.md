# 生物制造产业资讯追踪系统 MVP PRD

## 1. 产品概述

### 1.1 产品名称
生物制造产业资讯追踪系统 MVP

### 1.2 产品目标
构建一个面向生物制造产业的情报追踪系统，持续监控目标公司及行业公开信息源，识别最新资讯与关键变化，并将结果以结构化事件、变化记录和日报的形式输出给用户。

### 1.3 MVP 核心价值
- 自动汇总目标公司的最新公开资讯
- 自动识别与历史相比发生的关键变化
- 将零散信息加工成可阅读、可排序、可提醒的产业情报

### 1.4 目标用户
- 产业研究员
- 投资分析师
- 战略/BD 团队
- 企业竞争情报团队

## 2. 问题定义

当前生物制造产业公开信息分散在公司官网、新闻媒体、招聘页面、行业媒体和监管公告中。人工追踪存在以下问题：
- 信息源分散，更新频繁
- 人工检索成本高
- 难以持续发现“变化”而不只是“新文章”
- 难以对信息重要性进行快速排序

本产品希望解决的问题是：帮助用户围绕目标公司和细分赛道，持续发现值得关注的新增事件与状态变化。

## 3. MVP 范围

### 3.1 MVP 聚焦范围
- 追踪对象：30-50 家目标公司
- 行业方向：生物制造、发酵与蛋白制造平台
- 更新频率：每日 1-3 次
- 语言范围：中文优先，可兼容英文
- 数据源范围：官网新闻页、公司公告页、招聘页、行业媒体 RSS/文章页、监管公告页

### 3.2 MVP 不包含
- 全行业知识图谱
- 实时流式计算架构
- 复杂权限系统
- 全量多语言翻译
- 大规模社交媒体 API 接入
- 高复杂度预测模型

## 4. 用户故事

### 4.1 用户故事列表
- 作为产业研究员，我希望每天看到目标公司新增的重要资讯，以便快速掌握动态。
- 作为分析师，我希望知道某家公司相较于上周发生了什么变化，而不是重新读完所有新闻。
- 作为情报人员，我希望能按公司、赛道、事件类型筛选信息。
- 作为管理者，我希望收到每日摘要，快速定位高优先级事件。

## 5. 核心功能模块

### 5.1 监控对象管理
用于维护需要追踪的公司和相关配置。

功能点：
- 新增/编辑/停用公司
- 配置公司别名、关键词、赛道、地区
- 绑定数据源链接
- 配置抓取频率和启用状态

输出：
- 公司主数据
- 公司与数据源的映射关系

### 5.2 数据采集
按预设数据源抓取公开内容。

首批支持：
- RSS
- 官网新闻页/博客页
- 招聘页
- 行业媒体文章列表页
- 监管公告页

采集结果：
- 标题
- 链接
- 发布时间
- 来源名称
- 原始正文/页面文本
- 抓取时间

### 5.3 信息清洗与去重
对原始文档进行解析和标准化。

功能点：
- 正文提取
- 发布时间标准化
- URL 标准化
- 相似内容去重
- 公司命中识别
- 事件标签分类

事件标签首版建议：
- 融资
- 合作
- 扩产
- 招聘
- 监管
- 技术发布
- 专利/IP
- 市场/销售
- 高管变动
- 其他

### 5.4 变化检测
对比历史内容识别增量变化。

MVP 支持三类变化：
- 新增资讯：本次首次出现的新闻/公告/文章
- 页面变化：目标页面文本内容发生实质变化
- 招聘变化：新增岗位、岗位关闭、岗位方向变化

输出：
- 变化类型
- 变化摘要
- 变化前后对比摘要
- 变化发生时间

### 5.5 情报加工
将采集与变化结果转成用户可消费的情报。

功能点：
- 事件摘要生成
- 变化说明生成
- 重要性评分
- 关注原因说明

建议评分维度：
- 来源可信度
- 是否来自公司官网/监管机构
- 是否涉及融资金额/产能/工厂/商业化
- 是否涉及大客户/大药企合作
- 是否为连续出现的强信号

### 5.6 展示与通知
为用户提供查询与提醒。

MVP 交付形式：
- Dashboard
- 今日变化列表
- 公司详情页
- 每日报告
- 邮件通知

## 6. 页面设计建议

### 6.1 Dashboard
展示内容：
- 今日新增事件数
- 今日关键变化数
- 高优先级事件列表
- 按事件类型统计
- 按公司统计

### 6.2 公司详情页
展示内容：
- 公司基本信息
- 监控数据源
- 事件时间线
- 页面变化记录
- 招聘变化记录

### 6.3 报告页/日报
展示内容：
- 今日重点变化 Top N
- 按公司分组的新增事件
- 按类型分组的行业动态
- 建议重点关注名单

## 7. 业务流程

### 7.1 日常任务流
1. 调度器按计划触发采集任务
2. 采集器抓取目标数据源
3. 原始内容写入原始文档表
4. 清洗程序解析、去重、分类
5. 变化检测模块对比历史快照
6. 生成事件、变化记录、告警
7. Dashboard 展示并产生日报

### 7.2 变化检测逻辑
1. 针对固定页面保存最新快照
2. 新抓取内容与上次快照对比
3. 文本相似度低于阈值时判定为页面变化
4. 招聘页面中岗位集合发生变化时生成招聘变化
5. 新闻链接首次出现时生成新增资讯事件

## 8. 非功能需求

### 8.1 性能
- 支持 50 家公司、每家公司 3-5 个数据源的日常抓取
- 单轮抓取处理控制在 30 分钟内

### 8.2 稳定性
- 采集失败需记录日志
- 单数据源失败不影响整体任务
- 支持任务重试

### 8.3 可维护性
- 采集器按数据源类型解耦
- 分类规则与关键词可配置
- 每个模块应支持单独调试

### 8.4 合规
- 仅处理公开可访问信息
- 保留来源链接和抓取时间
- 避免违反目标站点 robots 或访问频率限制

## 9. MVP 成功指标

### 9.1 业务指标
- 每日成功抓取率 >= 85%
- 每日输出有效事件数可供人工审阅
- 高价值事件召回率达到人工可接受水平

### 9.2 产品指标
- 用户能在 5 分钟内浏览完每日重点变化
- 能通过公司详情页快速查看最近 30 天动态
- 重点事件排序基本符合人工直觉

## 10. 技术建议

推荐技术栈：
- 后端：Python + FastAPI
- 抓取：requests、BeautifulSoup、feedparser
- 动态网页：Playwright
- 调度：APScheduler
- 数据库：PostgreSQL
- 报告输出：Markdown / HTML
- AI 能力：摘要、分类、变化说明

---

# 数据库表设计

## 1. 设计原则
- 原始数据与业务数据分层存储
- 所有事件尽量可追溯到原始来源
- 页面变化和招聘变化保留快照，方便回放
- 公司、数据源、文档、事件、变化记录解耦

## 2. 表清单
- companies
- company_aliases
- sources
- crawl_runs
- raw_documents
- page_snapshots
- jobs
- job_snapshots
- events
- event_companies
- change_logs
- alerts

## 3. 详细表设计

### 3.1 companies
公司主表。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| name | varchar(255) | 公司名称 |
| english_name | varchar(255) | 英文名 |
| website | varchar(500) | 官网 |
| category | varchar(100) | 公司分类，如生物制造/蛋白平台 |
| sub_sector | varchar(100) | 细分赛道 |
| region | varchar(100) | 地区 |
| country | varchar(100) | 国家/地区 |
| description | text | 简介 |
| status | varchar(50) | active/inactive |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

建议索引：
- unique(name)
- index(category)
- index(status)

### 3.2 company_aliases
公司别名表，用于实体识别。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| company_id | bigint FK | 公司 ID |
| alias | varchar(255) | 别名 |
| alias_type | varchar(50) | 简称/英文名/品牌名 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(company_id)
- index(alias)

### 3.3 sources
数据源配置表。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| company_id | bigint FK nullable | 关联公司，可为空表示行业通用源 |
| source_name | varchar(255) | 数据源名称 |
| source_type | varchar(50) | rss/web/jobs/regulatory/media |
| url | varchar(1000) | 数据源 URL |
| parser_type | varchar(100) | 解析器类型 |
| crawl_frequency | varchar(50) | daily/6h/manual |
| is_active | boolean | 是否启用 |
| last_crawled_at | timestamp | 最近抓取时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

建议索引：
- index(company_id)
- index(source_type)
- index(is_active)

### 3.4 crawl_runs
抓取任务执行记录表。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| source_id | bigint FK | 数据源 ID |
| run_status | varchar(50) | success/failed/partial |
| started_at | timestamp | 开始时间 |
| finished_at | timestamp | 结束时间 |
| http_status | integer | HTTP 状态码 |
| item_count | integer | 抓取条数 |
| error_message | text | 错误信息 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(source_id)
- index(run_status)
- index(started_at)

### 3.5 raw_documents
原始文档表，保存抓取到的原始内容。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| source_id | bigint FK | 数据源 ID |
| crawl_run_id | bigint FK | 抓取任务 ID |
| doc_type | varchar(50) | news/article/job/page |
| title | varchar(1000) | 标题 |
| url | varchar(1500) | 文档链接 |
| published_at | timestamp nullable | 发布时间 |
| author | varchar(255) nullable | 作者 |
| content_text | text | 原始正文文本 |
| content_html | text nullable | 原始 HTML |
| content_hash | varchar(128) | 内容哈希 |
| language | varchar(20) | 语言 |
| metadata_json | jsonb | 扩展字段 |
| fetched_at | timestamp | 抓取时间 |
| created_at | timestamp | 创建时间 |

建议索引：
- unique(source_id, url)
- index(content_hash)
- index(published_at)
- gin(metadata_json)

### 3.6 page_snapshots
页面快照表，用于检测页面变化。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| source_id | bigint FK | 数据源 ID |
| raw_document_id | bigint FK | 原始文档 ID |
| page_url | varchar(1500) | 页面 URL |
| snapshot_text | text | 页面标准化文本 |
| snapshot_hash | varchar(128) | 快照哈希 |
| diff_base_snapshot_id | bigint nullable | 对比基准快照 ID |
| changed_ratio | numeric(5,2) nullable | 变化比例 |
| captured_at | timestamp | 抓取时间 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(source_id)
- index(page_url)
- index(snapshot_hash)

### 3.7 jobs
职位主表，用于维护当前识别到的岗位。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| company_id | bigint FK | 公司 ID |
| source_id | bigint FK | 来源数据源 ID |
| job_title | varchar(500) | 岗位名称 |
| location | varchar(255) nullable | 地点 |
| department | varchar(255) nullable | 部门 |
| status | varchar(50) | open/closed/unknown |
| first_seen_at | timestamp | 首次发现时间 |
| last_seen_at | timestamp | 最近发现时间 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

建议索引：
- index(company_id)
- index(job_title)
- index(status)

### 3.8 job_snapshots
职位快照表，用于记录某次抓取时的岗位集合和内容。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| source_id | bigint FK | 数据源 ID |
| crawl_run_id | bigint FK | 抓取任务 ID |
| snapshot_date | date | 快照日期 |
| jobs_json | jsonb | 岗位列表 |
| jobs_count | integer | 岗位数 |
| snapshot_hash | varchar(128) | 快照哈希 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(source_id)
- index(snapshot_date)
- gin(jobs_json)

### 3.9 events
结构化事件表，是展示和报告的核心。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| raw_document_id | bigint FK nullable | 来源原始文档 |
| source_id | bigint FK | 数据源 ID |
| event_type | varchar(100) | 融资/合作/扩产/招聘等 |
| title | varchar(1000) | 事件标题 |
| summary | text | 事件摘要 |
| importance_score | integer | 重要性评分 0-100 |
| confidence_score | numeric(5,2) | 识别置信度 |
| source_level | varchar(50) | official/media/regulatory |
| occurred_at | timestamp nullable | 事件发生时间 |
| event_url | varchar(1500) | 事件链接 |
| status | varchar(50) | new/processed/ignored |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

建议索引：
- index(event_type)
- index(importance_score)
- index(occurred_at)
- index(status)

### 3.10 event_companies
事件与公司多对多关系表。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| event_id | bigint FK | 事件 ID |
| company_id | bigint FK | 公司 ID |
| role_type | varchar(50) | subject/partner/mentioned |
| created_at | timestamp | 创建时间 |

建议索引：
- unique(event_id, company_id, role_type)
- index(company_id)

### 3.11 change_logs
变化记录表，是系统核心输出之一。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| company_id | bigint FK nullable | 关联公司 |
| source_id | bigint FK | 来源数据源 |
| change_type | varchar(100) | new_event/page_change/job_change |
| target_type | varchar(100) | page/job/news |
| target_id | bigint nullable | 关联对象 ID |
| title | varchar(1000) | 变化标题 |
| summary | text | 变化摘要 |
| before_value | text nullable | 变化前摘要 |
| after_value | text nullable | 变化后摘要 |
| changed_ratio | numeric(5,2) nullable | 变化比例 |
| importance_score | integer | 重要性评分 |
| detected_at | timestamp | 识别时间 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(company_id)
- index(change_type)
- index(detected_at)
- index(importance_score)

### 3.12 alerts
提醒记录表，用于日报、邮件和推送。

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | 主键 |
| alert_type | varchar(50) | daily_report/email/system |
| target_date | date | 目标日期 |
| title | varchar(500) | 提醒标题 |
| content | text | 提醒正文 |
| payload_json | jsonb | 附加内容 |
| send_status | varchar(50) | pending/sent/failed |
| sent_at | timestamp nullable | 发送时间 |
| created_at | timestamp | 创建时间 |

建议索引：
- index(alert_type)
- index(target_date)
- index(send_status)

## 4. 关键关系

- `companies 1:N sources`
- `sources 1:N crawl_runs`
- `sources 1:N raw_documents`
- `raw_documents 1:N events`
- `companies N:N events` 通过 `event_companies`
- `sources 1:N page_snapshots`
- `sources 1:N job_snapshots`
- `companies 1:N jobs`
- `companies 1:N change_logs`

## 5. 首版可简化实现

如果你要更快启动开发，数据库还可以先缩减为 8 张核心表：
- companies
- company_aliases
- sources
- raw_documents
- page_snapshots
- job_snapshots
- events
- change_logs

等 MVP 验证后，再补：
- crawl_runs
- jobs
- event_companies
- alerts

## 6. 后续扩展方向
- 增加监管审批、专利、融资数据库等专用数据源
- 增加用户订阅与权限体系
- 增加多语言翻译与统一归一化
- 增加知识图谱与公司关系网络
- 增加基于历史行为的重点变化推荐

