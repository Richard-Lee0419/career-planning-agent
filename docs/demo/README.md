# 当前发布验收（2026-10-12）

当前标准为`manual-pilot-2026-10-12-v2`。优先查看以下材料；本页下方保留初次v1演示和失败，不将旧截图或旧通过次数冒充本次结果。

- [六角色真实API核查](release-20261012/live-api-results.json)：五个角色完整通过，第六个注册触发429；[该剩余角色补验](release-remaining-role/live-api-results.json)通过。合计六个角色分别完成14步，分两批记录。
- [建议内容评审](release-evaluation.md)：逐项阅读任务、资源和下一项建议，明确助手评审及主观自查的限制。
- [真实Edge浏览器记录](release-browser/browser-results.json)：真实服务、独立会话、无API拦截；登录/图表、同域推荐、来源、路径恢复、进度双向刷新、原生下载，以及从界面生成新版本。
- [推荐与来源截图](release-browser/recommendations.png)、[已保存路径截图](release-browser/saved-roadmap.png)、[界面新生成路径截图](release-browser/generated-roadmap.png)、[浏览器下载的报告](release-browser/browser-export.md)。
- [收束范围前的失败记录](final-20261012/live-api-results.json)：模型仍生成过多任务，本轮主动中止；不是成功结果。

完整检查、环境、复现及限制见[验证记录](../validation.md)。下面的材料对应初次交付。

---

# B 方案演示证据索引

验收日期：2026-10-11–12，中国标准时间。全部输入为合成画像，服务使用隔离SQLite；没有真实用户效果或就业统计。本目录保留原始模型内容，其中仍有不适用的建议，不能当作已经审核的职业指导。

## 当前交付

| 材料 | 已验证内容及边界 |
| --- | --- |
| [最终真实API记录](live-api-results.json) | 内容运营、招聘助理各14步HTTP流程通过；含输入、断言、真实模型计划、顾问回复和恢复记录。模型配置名不等于服务商元数据核验；两案例不构成准确率/可用性评价。 |
| [内容运营报告](content-operations-report.md) | 版本#4，37%规则参考及生成时来源快照；任务仍可能重复已填报能力，需人工评审。 |
| [招聘助理报告](recruiting-assistant-report.md) | 版本#5，50%规则参考、一项已完成、一项待办、来源版本和任务。 |
| [浏览器收尾记录](browser-results.json) | 未拦截API；同领域卡片、切换领域保留主目标、真实历史版本、UI进度、来源链接和导出验证。恢复的是API真实生成版本，另一次UI生成被拒绝，不能写成新用户浏览器全过程成功。 |
| [浏览器取回报告](recruiting-browser-report.md) | 经浏览器网络取得版本#5的Markdown，HTTP 200、3492字节；画像、任务、进度和来源与API报告一致，导出时间及验收脚本添加的合成标注不同，文件字节不相同。不等于验证原生下载目录落盘。 |
| [岗位覆盖页面截图](screenshots/hr-recommendations.png) | 招聘助理当前目标、已填报能力、50%覆盖参考与差距；为实际可见区域，未包含整页三张卡片。 |
| [历史来源展开截图](screenshots/recruiting-source.png) | 版本#5、来源版本、工作任务、教育部和雇主链接、核对范围及限制；整页捕获降级为实际可见区域。 |

截图均来自真实页面，并已打开检查；没有拦截所有API或注入成功结果。任务页截图捕获曾超时，因此任务和进度证据以浏览器状态记录、API恢复及导出内容为准，不能把缺失截图当作已经提供的材料。

操作与复现见[演示步骤](../demo-walkthrough.md)，完整环境、命令、失败和人工阅读结论见[验证记录](../validation.md)。本地自动化最终结果为后端64项、前端8项通过及lint/构建成功；外部AI在自动化中被替换，真实服务结果单独记录。

## 保留的历史运行

| 历史材料 | 含义 |
| --- | --- |
| [提示词修复前](live-api-results-before-prompt-fix.json)、[内容报告](content-operations-report-before-prompt-fix.md)、[招聘失败](recruiting-assistant-failure-before-prompt-fix.md) | 无来源认证/笼统任务以及30秒模型配置下的504超时；不是当前成功报告。 |
| [结构任务约束前](live-api-results-before-structured-tasks.json)、[内容报告](content-operations-report-before-structured-tasks.md)、[招聘报告](recruiting-assistant-report-before-structured-tasks.md) | HTTP流程通过但任务缺少具体产出、自查和估时；不能当作生成质量通过。 |
| [资源归一前](live-api-results-before-resource-normalization.json)、[内容失败](content-operations-failure-before-resource-normalization.md)、[招聘失败](recruiting-assistant-failure-before-resource-normalization.md) | 两案例路径结构校验返回502；浏览器复现定位资源对象/字符串不一致后做了归一修复。两次API失败没有充分细节证明原因完全相同。 |
| [沙箱网络受限记录](live-api-results-sandbox-blocked.json) | 当时未能连接本机服务的环境限制，不是模型输出，也未记作通过。 |

`pre-final-success/` 是结构任务约束前报告的备份，`*-report-failure.md` 是资源归一前的失败摘要；它们均为历史材料。当前结果使用本页“当前交付”中的无后缀JSON/报告，不能混用历史版本。

## 尚需人工判断

来源核对不代表从业者评审，标准覆盖参考不代表职业适合度，结构合格不代表学习建议正确。当前原文仍有重复已掌握能力、假定可用导师、从有限材料概括“最佳实践”、顾问跳过待办的问题。下一轮应先按这些具体失败建立少量人工评审案例，再决定模型提示词、任务生成或进度上下文的改动。
