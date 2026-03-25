# 需求文档

## 简介

抖音带货自动化系统旨在帮助内容创作者和电商运营者，通过自动化手段发现爆款商品、采集素材、分析文案、生成带货视频，并最终自动发布至抖音平台并挂载商品链接，实现全流程无人值守的带货运营。

## 词汇表

- **系统（System）**：抖音带货自动化系统整体
- **爬虫模块（Crawler）**：负责从抖音平台抓取商品和视频数据的模块
- **商品分析器（Product_Analyzer）**：负责分析商品热度、销量等指标，识别爆款商品的模块
- **素材采集器（Material_Collector）**：负责下载商品图片、视频等素材的模块
- **文案分析器（Content_Analyzer）**：负责提取和分析视频标题、文案、话题标签的模块
- **内容生成器（Content_Generator）**：负责利用 AI 重绘图片、生成或改编带货视频的模块
- **发布器（Publisher）**：负责将生成的视频自动发布至抖音并挂载商品链接的模块
- **调度器（Scheduler）**：负责协调各模块按流程顺序执行任务的模块
- **爆款商品（Trending_Product）**：在抖音平台上销量增长迅速、互动数据优异的商品
- **带货视频（Commerce_Video）**：包含商品推广内容并挂载商品链接的短视频
- **话题标签（Hashtag）**：抖音视频中以 # 开头的话题标记

---

## 需求

### 需求 1：爆款商品发现

**用户故事：** 作为电商运营者，我希望系统能自动发现抖音平台上的爆款商品，以便我能及时跟进热销品类，提升带货成功率。

#### 验收标准

1. THE Crawler SHALL 定期从抖音平台抓取商品销量、点赞数、评论数、分享数等互动指标数据。
2. WHEN 抓取任务完成时，THE Product_Analyzer SHALL 根据销量增长率、互动数据综合评分，筛选出评分前 20% 的商品作为爆款商品候选列表。
3. WHEN 爆款商品候选列表生成后，THE Product_Analyzer SHALL 按综合评分从高到低排序并输出结果。
4. THE System SHALL 支持按商品类目（如美妆、服饰、食品）过滤爆款商品列表。
5. IF 抖音平台接口返回错误或请求被限流，THEN THE Crawler SHALL 记录错误日志并在 60 秒后自动重试，最多重试 3 次。
6. WHILE 爬虫任务执行中，THE Crawler SHALL 将请求频率控制在每分钟不超过 30 次，以避免触发平台反爬机制。

---

### 需求 2：素材采集

**用户故事：** 作为内容创作者，我希望系统能自动采集爆款商品的图片和视频素材，以便我有充足的原始素材用于内容再创作。

#### 验收标准

1. WHEN 爆款商品列表确定后，THE Material_Collector SHALL 自动下载每个商品关联的全部商品图片（不少于 3 张）及带货视频（不少于 1 个）。
2. THE Material_Collector SHALL 将采集到的素材按商品 ID 分类存储至本地指定目录。
3. IF 某商品的图片或视频资源无法访问，THEN THE Material_Collector SHALL 跳过该资源并在采集报告中标记为"采集失败"。
4. THE Material_Collector SHALL 在采集完成后生成采集报告，报告中包含成功数量、失败数量及失败原因。
5. THE Material_Collector SHALL 对已采集的素材进行去重，避免重复下载相同资源。
6. WHEN 素材文件下载完成后，THE Material_Collector SHALL 校验文件完整性（通过文件大小或哈希值），IF 文件不完整，THEN THE Material_Collector SHALL 重新下载该文件。

---

### 需求 3：文案分析

**用户故事：** 作为内容创作者，我希望系统能自动分析爆款视频的文案、标题和话题标签，以便我了解高转化内容的写作规律。

#### 验收标准

1. WHEN 视频素材采集完成后，THE Content_Analyzer SHALL 提取每个视频的标题、正文文案及全部话题标签。
2. THE Content_Analyzer SHALL 对提取的文案进行关键词频率统计，输出出现频率最高的前 20 个关键词。
3. THE Content_Analyzer SHALL 识别并统计各视频中使用的话题标签，输出使用频率最高的前 10 个话题标签。
4. THE Content_Analyzer SHALL 分析视频标题的结构模式（如疑问句、数字列表、情感词），并输出各模式的占比统计。
5. IF 视频文案为空或无法提取，THEN THE Content_Analyzer SHALL 跳过该视频并在分析报告中标注"文案缺失"。
6. THE Content_Analyzer SHALL 将分析结果以结构化格式（JSON）输出，供内容生成器调用。

---

### 需求 4：内容再创作

**用户故事：** 作为内容创作者，我希望系统能基于采集的素材和文案分析结果，利用 AI 自动生成原创带货视频，以便规避版权风险并提升内容差异化。

#### 验收标准

1. WHEN 素材采集和文案分析均完成后，THE Content_Generator SHALL 基于商品图片生成经过 AI 重绘处理的新图片，使其与原图视觉风格有明显差异。
2. THE Content_Generator SHALL 基于文案分析结果和商品信息，自动生成带货视频脚本，脚本长度在 15 秒至 60 秒之间。
3. THE Content_Generator SHALL 将生成的脚本、重绘图片及背景音乐合成为带货视频，视频分辨率不低于 1080×1920（竖屏）。
4. THE Content_Generator SHALL 基于文案分析中的高频关键词和话题标签，自动生成视频标题和配套文案。
5. IF AI 重绘或视频合成过程中发生错误，THEN THE Content_Generator SHALL 记录错误详情并跳过当前商品，继续处理下一个商品。
6. WHERE 用户启用人工审核模式，THE Content_Generator SHALL 在生成内容后暂停流程，等待用户确认后再继续。
7. THE Content_Generator SHALL 确保生成的视频文案不包含违禁词，违禁词列表由用户配置。

---

### 需求 5：自动发布与商品挂载

**用户故事：** 作为电商运营者，我希望系统能将生成的带货视频自动发布至抖音并挂载商品链接，以便实现全流程自动化运营，节省人工操作时间。

#### 验收标准

1. WHEN 带货视频生成完成并通过审核后，THE Publisher SHALL 将视频自动上传至抖音平台。
2. WHEN 视频上传成功后，THE Publisher SHALL 自动挂载对应的商品链接至该视频。
3. THE Publisher SHALL 支持按用户配置的发布时间表（如每天 10:00、18:00、21:00）定时发布视频。
4. IF 视频上传失败，THEN THE Publisher SHALL 记录失败原因并在 5 分钟后重试，最多重试 3 次。
5. IF 商品链接挂载失败，THEN THE Publisher SHALL 记录失败原因并通知用户手动处理。
6. THE Publisher SHALL 在每次发布完成后记录发布日志，日志包含视频 ID、发布时间、商品链接及发布状态。
7. WHILE 发布任务执行中，THE Publisher SHALL 维护抖音账号的登录态，IF 登录态失效，THEN THE Publisher SHALL 暂停发布任务并通知用户重新登录。

---

### 需求 6：全流程调度与监控

**用户故事：** 作为系统管理员，我希望系统能自动协调各模块按顺序执行，并提供运行状态监控，以便我能掌握整体运行情况并及时处理异常。

#### 验收标准

1. THE Scheduler SHALL 按照"爬取 → 分析 → 采集 → 文案分析 → 内容生成 → 发布"的顺序自动调度各模块执行。
2. WHEN 任意模块执行失败时，THE Scheduler SHALL 记录失败信息并根据配置决定是跳过当前任务继续执行，还是暂停整个流程等待人工介入。
3. THE System SHALL 提供 Web 控制台，展示各模块的实时运行状态、任务队列及历史执行记录。
4. THE System SHALL 支持用户通过 Web 控制台手动触发或停止任意模块的执行。
5. WHEN 任意模块连续失败超过 5 次时，THE Scheduler SHALL 向用户发送告警通知（支持邮件或 Webhook）。
6. THE System SHALL 保留最近 30 天的任务执行日志，供用户查询和审计。
