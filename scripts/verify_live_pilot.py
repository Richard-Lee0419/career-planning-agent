"""Verify two synthetic non-IT journeys against a running local, real-AI API.

This is an opt-in integration check, not a model-quality benchmark. It creates
two accounts in the selected local service and consumes real model requests.
Run it against an isolated database; it never reads .env or stores credentials.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import secrets
import sys
import time
from urllib.parse import urlsplit
import uuid

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
CHINA_TIME = timezone(timedelta(hours=8))
PLANNED_STEPS = [
    "register", "login", "extract_profile", "restore_profile", "domain_recommendations",
    "gap_analysis", "generate_roadmap", "restore_saved_roadmap", "save_task_progress",
    "restore_task_progress", "create_bound_session", "chat", "restore_chat", "export_report",
]
CASES = [
    {
        "domain": "marketing_content", "role": "内容运营", "major": "市场营销",
        "skills": ["文案撰写", "图文排版"], "expected_matched_skills": ["文案写作", "图文编辑"],
        "interests": ["内容传播"], "name": "合成内容同学",
        "experience": "合成演示资料：在课程活动中练习文案撰写和图文排版，与团队合作完成一份活动宣传稿。不是实际用户履历。",
        "report_filename": "content-operations-report.md",
    },
    {
        "domain": "human_resources", "role": "招聘助理", "major": "人力资源管理",
        "skills": ["Excel", "简历初筛", "面试安排"], "expected_matched_skills": ["电子表格", "简历筛选", "面试协调"],
        "interests": ["招聘与培训"], "name": "合成招聘同学",
        "experience": "合成演示资料：在课程作业中用虚构简历练习初筛，用Excel整理候选人表并安排模拟面试；与团队合作。不含真实候选人信息。",
        "report_filename": "recruiting-assistant-report.md",
    },
]


def timestamp() -> str:
    return datetime.now(CHINA_TIME).isoformat(timespec="seconds")


def local_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or
            parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in {"", "/"}):
        raise argparse.ArgumentTypeError("base URL must be a localhost origin, without credentials or a path")
    return value.rstrip("/")


def safe_data(value):
    """Remove credential-shaped keys, including from validation error inputs."""
    if isinstance(value, dict):
        return {key: safe_data(item) for key, item in value.items()
                if not re.search(r"password|token|secret|api.?key|authorization|^input$", str(key), re.I)}
    if isinstance(value, list):
        return [safe_data(item) for item in value]
    return value


class VerificationFailure(RuntimeError):
    pass


class Verifier:
    def __init__(self, base_url: str, output_dir: Path, model: str, http_timeout: float, backend_ai_timeout: float | None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.started = time.perf_counter()
        self.expected_case_count = len(CASES)
        self.results = {
            "started_at": timestamp(), "finished_at": None, "status": "running",
            "base_url": base_url, "http_timeout_seconds": http_timeout,
            "backend_ai_timeout_seconds": backend_ai_timeout,
            "backend_timeout_evidence": "Operator-supplied runtime configuration, not measured by the API client.",
            "configured_model": model,
            "model_evidence": "Model configuration supplied by the operator for this backend; this API does not expose the provider response model metadata.",
            "environment": {"python": platform.python_version(), "httpx": httpx.__version__,
                            "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            "evidence_boundary": [
                "Only synthetic profiles and isolated local service accounts are used.",
                "No API key, bearer token, account password, or .env content is saved.",
                "Real API/model integration is checked; recommendation accuracy and generated advice quality are not measured.",
                "Each case uses four AI HTTP endpoints without client retries; learning-path has two model calls and gap may retry once on malformed output. SDK transport retries/fallback are not observable here.",
                "Generated plans, resources and advice require manual review; no quality or hiring-effect claim follows from passing HTTP checks.",
            ],
            "catalog": None, "cases": [],
        }
        self.client = httpx.Client(base_url=base_url, timeout=http_timeout, trust_env=False, follow_redirects=False)
        self.write_results()

    def write_results(self):
        temporary = self.output_dir / "live-api-results.json.tmp"
        temporary.write_text(json.dumps(safe_data(self.results), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.output_dir / "live-api-results.json")

    def request(self, case: dict, name: str, method: str, path: str, *, ai=False, **kwargs):
        step = {"name": name, "method": method, "path": path, "started_at": timestamp(), "status": "running"}
        case["steps"].append(step)
        if ai:
            case["ai_http_requests"] += 1
            if case["ai_http_requests"] > 4:
                raise VerificationFailure("the four AI-endpoint budget was exceeded")
        self.write_results()
        started = time.perf_counter()
        try:
            response = self.client.request(method, path, **kwargs)
            step["http_status"] = response.status_code
            if not 200 <= response.status_code < 300:
                try:
                    step["error_response"] = safe_data(response.json())
                except ValueError:
                    step["error_response"] = "Non-JSON error body omitted to avoid saving reflected credentials."
                raise VerificationFailure(f"{name} returned HTTP {response.status_code}")
            step["status"] = "passed"
            return response
        except (httpx.HTTPError, VerificationFailure) as error:
            step["status"] = "failed"
            step["error"] = str(error)
            raise VerificationFailure(f"{name}: {error}") from error
        finally:
            step["duration_seconds"] = round(time.perf_counter() - started, 3)
            self.write_results()
            print(f"{case['domain']}: {name} {step['status']} HTTP {step.get('http_status', 'none')} ({step['duration_seconds']}s)", flush=True)

    def check(self, case: dict, name: str, condition: bool, evidence=None):
        item = {"name": name, "status": "passed" if condition else "failed"}
        if evidence is not None:
            item["evidence"] = safe_data(evidence)
        case["checks"].append(item)
        self.write_results()
        if not condition:
            raise VerificationFailure(name)

    def read_catalog(self):
        # Only the non-AI readiness request is retried if the operator restarts the service.
        failure = None
        for attempt in range(4):
            try:
                response = self.client.get("/api/career/catalog")
                response.raise_for_status()
                catalog = response.json()
                expected_roles = {item["role"] for item in CASES}
                if not expected_roles.issubset({item["role_name"] for item in catalog["roles"]}):
                    raise VerificationFailure("the selected backend does not contain the two pilot targets")
                self.results["catalog"] = catalog
                self.write_results()
                return
            except (httpx.HTTPError, ValueError, KeyError, VerificationFailure) as error:
                failure = str(error)
                if attempt < 3:
                    time.sleep(5)
        raise VerificationFailure(f"local service readiness failed: {failure}")

    def run_case(self, spec: dict):
        assessment = {
            "name": spec["name"], "education_level": "本科", "major": spec["major"], "grade": "大三",
            "location": "中国大陆", "current_skills": spec["skills"], "soft_skills": ["团队合作"],
            "certificates": [], "target_roles": [spec["role"]], "interests": spec["interests"],
            "internship_experience": spec["experience"], "weekly_learning_time": "每周 6-10 小时",
        }
        case = {"domain": spec["domain"], "target_role": spec["role"], "synthetic_assessment": assessment,
                "status": "running", "steps": [], "checks": [], "ai_http_requests": 0,
                "content_review": {"manual_review_required": True, "automatic_quality_score": None}}
        self.results["cases"].append(case)
        password = secrets.token_urlsafe(24) + "Aa1!"
        username = f"pilot_live_{spec['domain']}_{uuid.uuid4().hex[:10]}"
        try:
            self.request(case, "register", "POST", "/api/auth/register", json={"username": username, "password": password})
            login = self.request(case, "login", "POST", "/api/auth/login", data={"username": username, "password": password}).json()
            token = login["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            resume = (f"这是合成演示画像，不是真实用户。姓名：{spec['name']}；本科大三；专业：{spec['major']}；"
                      f"当前技能：{'、'.join(spec['skills'])}；软素质：团队合作；目标：{spec['role']}；"
                      f"兴趣：{'、'.join(spec['interests'])}；经历：{spec['experience']}；"
                      "无证书、无正式实习。每周可学习6-10小时。不要添加未提供的经历或能力。")
            extracted = self.request(case, "extract_profile", "POST", "/api/user/profile/extract", ai=True,
                                     headers=headers, json={"resume_text": resume, "assessment": assessment}).json()
            case["profile_extraction"] = extracted
            profile = self.request(case, "restore_profile", "GET", "/api/profile/me", headers=headers).json()
            case["restored_profile"] = profile
            for key in ("major", "current_skills", "soft_skills", "target_roles", "weekly_learning_time"):
                self.check(case, f"explicit_{key}_preserved", profile.get(key) == assessment[key], profile.get(key))
            recommendations = self.request(case, "domain_recommendations", "GET", "/api/recommendations",
                                           headers=headers, params={"domain": spec["domain"]}).json()
            case["recommendations"] = recommendations
            matches = recommendations["data"]
            self.check(case, "only_selected_domain_returned", bool(matches) and all(item["domain"] == spec["domain"] for item in matches), [item["role_name"] for item in matches])
            target = next((item for item in matches if item["role_name"] == spec["role"]), None)
            self.check(case, "target_has_evidence_score", target is not None and isinstance(target.get("score"), (int, float)), target)
            self.check(case, "explicit_aliases_match_only_recorded_requirements", set(target["matched_skills"]) == set(spec["expected_matched_skills"]), target["matched_skills"])
            source = target["standard_source"]
            self.check(case, "pilot_source_is_recorded", source.get("type") == "manual_pilot" and source.get("review_status") == "source_checked" and bool(source.get("sources")), source)
            gap = self.request(case, "gap_analysis", "POST", "/api/agent/gap-analysis", ai=True,
                               headers=headers, params={"target_role": spec["role"]}).json()
            case["gap_analysis"] = gap
            self.check(case, "gap_does_not_replace_deterministic_score", gap["overall_match_score"] == target["score"], {"recommendation": target["score"], "gap": gap["overall_match_score"]})
            self.check(case, "gap_keeps_source", gap.get("standard_source") == source)
            roadmap = self.request(case, "generate_roadmap", "POST", "/api/agent/learning-path", ai=True,
                                   headers={**headers, "Idempotency-Key": uuid.uuid4().hex}, params={"target_role": spec["role"]}).json()
            case["generated_roadmap"] = roadmap
            self.check(case, "generated_plan_has_tasks_and_source", isinstance(roadmap.get("id"), int) and roadmap.get("target_role") == spec["role"] and roadmap.get("standard_source") == source and bool(roadmap.get("milestones")) and all(item.get("focus_targets") for item in roadmap["milestones"]))
            stage_evidence = []
            expected_start = 1
            self.check(case, "pilot_plan_is_bounded", len(roadmap["milestones"]) <= 2 and all(len(stage["focus_targets"]) <= 2 for stage in roadmap["milestones"]))
            for stage in roadmap["milestones"]:
                period = re.fullmatch(r"第(\d+)(?:[–—-](\d+))?周", stage["period"])
                self.check(case, "stage_uses_contiguous_bounded_weeks", period is not None and int(period.group(1)) == expected_start and int(period.group(2) or period.group(1)) <= 4, stage["period"])
                end = int(period.group(2) or period.group(1))
                weeks = end - expected_start + 1
                hours = 0.0
                for text in stage["focus_targets"]:
                    fields = re.fullmatch(r"(.+)；产出：(.+)；自查：(.+)；预计(\d+(?:\.\d+)?)小时", text)
                    self.check(case, "task_has_action_deliverable_self_check_and_hours", fields is not None and all(value.strip() for value in fields.groups()), text)
                    hours += float(fields.group(4))
                self.check(case, "stage_hours_fit_synthetic_weekly_budget", weeks >= 1 and 0 < hours <= 10 * weeks, {"stage": stage["phase"], "weeks": weeks, "estimated_task_hours": hours, "weekly_budget_upper_bound": 10})
                stage_evidence.append({"phase": stage["phase"], "weeks": weeks, "estimated_task_hours": hours})
                expected_start = end + 1
            case["content_review"]["task_structure_and_budget"] = stage_evidence
            approved_urls = [ref["url"] for ref in source["sources"]]
            resources = [resource for stage in roadmap["milestones"] for resource in stage["recommended_resources"]]
            self.check(case, "resources_use_only_recorded_source_urls", all(any(url in resource for url in approved_urls) for resource in resources), resources)
            task_texts = [task for stage in roadmap["milestones"] for task in stage["focus_targets"]]
            allowed = target["missing_skills"] + target["missing_soft_skills"]
            if not allowed:
                allowed = target["matched_skills"] + target["matched_soft_skills"]
            self.check(case, "tasks_target_unmatched_capabilities", all(
                any(text.startswith(f"能力：{skill}；") for skill in allowed) for text in task_texts), task_texts)
            self.check(case, "no_unverified_qualification_tasks", not any(re.search(r"认证|考证|资格证|执照", text) for text in task_texts), task_texts)
            roadmap_id = roadmap["id"]
            detail = self.request(case, "restore_saved_roadmap", "GET", f"/api/history/roadmaps/{roadmap_id}", headers=headers).json()
            self.check(case, "saved_plan_restores_generated_content", all(detail.get(key) == roadmap.get(key) for key in ("target_role", "summary", "milestones", "conclusion", "standard_source", "standard_notice")))
            task = roadmap["milestones"][0]["focus_targets"][0]
            task_key = f"{roadmap['milestones'][0]['phase']}::{task}"
            self.request(case, "save_task_progress", "PUT", f"/api/history/roadmaps/{roadmap_id}/progress", headers=headers, json={"completed_tasks": [task_key]})
            restored = self.request(case, "restore_task_progress", "GET", f"/api/history/roadmaps/{roadmap_id}", headers=headers).json()
            case["restored_roadmap"] = restored
            self.check(case, "task_progress_survives_restore", restored.get("completed_tasks") == [task_key], restored.get("completed_tasks"))
            session = self.request(case, "create_bound_session", "POST", "/api/chat/sessions", headers=headers,
                                   json={"target_role": spec["role"], "roadmap_id": roadmap_id}).json()
            prompt = "请基于已保存路径和已勾选任务，给我下一项本周行动。注明这是有限标准试点，不要虚构招聘热度、薪资或资格承诺，不要建议转向编程。"
            chat = self.request(case, "chat", "POST", "/api/agent/chat", ai=True, headers=headers,
                                json={"session_id": session["id"], "message": prompt, "request_id": uuid.uuid4().hex, "target_role": spec["role"], "roadmap_id": roadmap_id}).json()
            case["chat_response"] = chat
            recovered = self.request(case, "restore_chat", "GET", f"/api/chat/sessions/{session['id']}", headers=headers).json()
            case["restored_chat"] = recovered
            self.check(case, "bound_chat_and_reply_survive_restore", recovered.get("target_role") == spec["role"] and recovered.get("roadmap_id") == roadmap_id and bool(chat.get("reply")) and any(item["role"] == "assistant" and item["content"] == chat["reply"] for item in recovered.get("messages", [])))
            report = self.request(case, "export_report", "POST", "/api/report/export", headers=headers,
                                  params={"target_role": spec["role"], "roadmap_id": roadmap_id}).text
            self.check(case, "export_keeps_selected_version_profile_source_and_task", f"#{roadmap_id}" in report and spec["major"] in report and spec["role"] in report and source["version"] in report and f"[x] {task}" in report and all(ref["url"] in report for ref in source["sources"]))
            report_path = self.output_dir / spec["report_filename"]
            report_path.write_text("<!-- Synthetic-profile integration demo; generated advice has not been quality-scored. -->\n" + report, encoding="utf-8")
            case["report_file"] = report_path.name
            generated_sections = [roadmap["summary"], roadmap["conclusion"], chat["reply"]]
            generated_sections += [text for phase in roadmap["milestones"] for text in phase["focus_targets"] + phase["recommended_resources"]]
            generated_text = "\n".join(generated_sections)
            case["content_review"]["programming_terms_for_manual_review"] = sorted(set(re.findall(r"Python|JavaScript|React|GitHub|开源项目|编程", generated_text, re.I)))
            case["content_review"]["qualification_claims_for_manual_review"] = [text for text in generated_sections if re.search(r"认证|证书|资格|执照|考试", text)]
            case["content_review"]["generated_resource_references"] = [resource for phase in roadmap["milestones"] for resource in phase["recommended_resources"]]
            case["status"] = "passed"
        except (VerificationFailure, KeyError, TypeError, ValueError) as error:
            case["status"] = "failed"
            case["error"] = f"{type(error).__name__}: {error}"
            executed = {step["name"] for step in case["steps"]}
            for name in PLANNED_STEPS:
                if name not in executed:
                    case["steps"].append({"name": name, "status": "skipped", "reason": "A prerequisite failed; no AI requests are retried by this verifier."})
            failure_path = self.output_dir / (Path(spec["report_filename"]).stem + "-failure.md")
            failure_lines = ["# 合成画像真实 API 验证失败记录", "", "这不是应用导出的规划报告。核心流程未完成，不能作为完整成功演示。", "",
                             f"- 记录时间：{timestamp()}", f"- 领域：{spec['domain']}", f"- 合成目标：{spec['role']}",
                             f"- 失败：{case['error']}", "", "## 合成输入", "", "```json",
                             json.dumps(assessment, ensure_ascii=False, indent=2), "```", "", "## 未完成步骤", ""]
            failure_lines += [f"- {step['name']}：{step['status']}" for step in case["steps"] if step["status"] != "passed"]
            failure_path.write_text("\n".join(failure_lines) + "\n", encoding="utf-8")
            case["failure_note_file"] = failure_path.name
        finally:
            # Credentials remain local variables and are never included in result data.
            self.write_results()

    def close(self):
        self.results["finished_at"] = timestamp()
        self.results["duration_seconds"] = round(time.perf_counter() - self.started, 3)
        if self.results["status"] == "running":
            self.results["status"] = "passed" if len(self.results["cases"]) == self.expected_case_count and all(case["status"] == "passed" for case in self.results["cases"]) else "failed"
        self.write_results()
        self.client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=local_base_url, default="http://127.0.0.1:8011")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "docs" / "demo")
    parser.add_argument("--model", default="glm-4-flash", help="Configured backend model label; no provider model metadata is exposed by this API")
    parser.add_argument("--http-timeout", type=float, default=120, help="HTTP timeout in seconds; default 120")
    parser.add_argument("--backend-ai-timeout", type=float, help="Operator-supplied backend AI timeout for the evidence log")
    parser.add_argument("--all-roles", action="store_true", help="Also verify the other four synthetic pilot targets; consumes more real model calls")
    parser.add_argument("--roles", nargs="+", help="Only these targets; use --all-roles to select targets beyond the default two. The service allows five registrations per IP per hour.")
    args = parser.parse_args()
    if args.http_timeout <= 0 or (args.backend_ai_timeout is not None and args.backend_ai_timeout <= 0):
        parser.error("timeouts must be positive")
    verifier = Verifier(args.base_url, args.output_dir, args.model, args.http_timeout, args.backend_ai_timeout)
    try:
        verifier.read_catalog()
        cases = list(CASES)
        if args.all_roles:
            known_roles = {spec["role"] for spec in cases}
            for role in verifier.results["catalog"]["roles"]:
                if role["standard_source"]["type"] != "manual_pilot" or role["role_name"] in known_roles:
                    continue
                skills = role["core_skills"][:2]
                cases.append({"domain": role["domain"], "role": role["role_name"],
                    "major": "市场营销" if role["domain"] == "marketing_content" else "人力资源管理",
                    "skills": skills, "expected_matched_skills": skills, "interests": [],
                    "name": "合成试点同学", "experience": "仅在虚构课程材料中练习已填报的两项技能，没有真实雇主、候选人或导师可参与。",
                    "report_filename": f"{role['role_id']}-report.md"})
        if args.roles:
            selected = set(args.roles)
            available = {case["role"] for case in cases}
            if selected - available:
                raise VerificationFailure("selected targets are not available; additional targets require --all-roles")
            cases = [case for case in cases if case["role"] in selected]
        verifier.expected_case_count = len(cases)
        verifier.results["expected_case_count"] = len(cases)
        for spec in cases:
            verifier.run_case(spec)
    except (VerificationFailure, KeyboardInterrupt) as error:
        verifier.results["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        verifier.results["error"] = str(error) or "Interrupted by operator"
    finally:
        verifier.close()
    print(f"Verification {verifier.results['status']}; results: {args.output_dir / 'live-api-results.json'}", flush=True)
    return 0 if verifier.results["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
