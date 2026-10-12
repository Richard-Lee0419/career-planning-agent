# 合成画像真实 API 验证失败记录

这不是应用导出的规划报告。核心流程未完成，不能作为完整成功演示。

- 记录时间：2026-10-12T00:30:33+08:00
- 领域：human_resources
- 合成目标：招聘助理
- 失败：VerificationFailure: generate_roadmap: generate_roadmap returned HTTP 502

## 合成输入

```json
{
  "name": "合成招聘同学",
  "education_level": "本科",
  "major": "人力资源管理",
  "grade": "大三",
  "location": "中国大陆",
  "current_skills": [
    "Excel",
    "简历初筛",
    "面试安排"
  ],
  "soft_skills": [
    "团队合作"
  ],
  "certificates": [],
  "target_roles": [
    "招聘助理"
  ],
  "interests": [
    "招聘与培训"
  ],
  "internship_experience": "合成演示资料：在课程作业中用虚构简历练习初筛，用Excel整理候选人表并安排模拟面试；与团队合作。不含真实候选人信息。",
  "weekly_learning_time": "每周 6-10 小时"
}
```

## 未完成步骤

- generate_roadmap：failed
- restore_saved_roadmap：skipped
- save_task_progress：skipped
- restore_task_progress：skipped
- create_bound_session：skipped
- chat：skipped
- restore_chat：skipped
- export_report：skipped
