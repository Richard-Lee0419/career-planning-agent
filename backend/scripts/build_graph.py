# scripts/build_graph.py
import os
import json
import sys

# 确保脚本能找到项目根目录的核心模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from zhipuai import ZhipuAI
from core.database import SessionLocal, engine
from models.db_models import Base, DBJobStandardProfile, DBJobRelation

# 加载环境变量并初始化 AI
load_dotenv()
client = ZhipuAI(api_key=os.getenv("ZHIPUAI_API_KEY"))

# 确保表结构存在
Base.metadata.create_all(bind=engine)

# 我们挑选15个互联网/软件行业核心岗位作为图谱节点
CORE_ROLES = [
    "前端开发工程师", "Java后端开发", "UI/UX设计师", "产品经理", "软件测试工程师",
    "数据分析师", "算法工程师", "运维工程师", "项目经理", "全栈工程师",
    "架构师", "技术总监", "数据产品经理", "移动端开发(iOS/Android)", "交互设计师"
]


def generate_profile_and_relations(role_name: str):
    print(f"🔄 正在请 AI 提炼岗位: 【{role_name}】 的图谱数据...")

    system_prompt = (
        "你是一个资深的互联网HR专家和大数据分析师。请为指定的岗位生成标准画像和关联路径。\n"
        "要求：必须严格返回 JSON，不要包含 ```json 标签。\n"
        "结构如下：\n"
        "{\n"
        "  \"role_name\": \"岗位名\",\n"
        "  \"description\": \"一句话描述\",\n"
        "  \"core_skills\": [\"技能1\", \"技能2\"],\n"
        "  \"soft_skills\": [\"软素质1\", \"软素质2\"],\n"
        "  \"certifications\": [\"证书1\"],\n"
        "  \"promotions\": [{\"target\": \"晋升岗位名\", \"weight\": 80}],\n"
        "  \"transfers\": [{\"target\": \"平调/换岗名\", \"weight\": 60}]\n"
        "}"
    )

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": f"请生成【{role_name}】的画像及路径数据。注意关联岗位最好在我们常见的IT岗位内。"}
            ],
            temperature=0.2
        )

        # 清洗并解析 JSON
        raw_json = response.choices[0].message.content.strip()
        cleaned_json = raw_json.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_json)
    except Exception as e:
        print(f"❌ 岗位 {role_name} 生成失败: {e}")
        return None


def main():
    db = SessionLocal()

    for role in CORE_ROLES:
        # 1. 检查是否已经生成过，防止重复跑
        existing_profile = db.query(DBJobStandardProfile).filter(DBJobStandardProfile.role_name == role).first()
        if existing_profile:
            print(f"✅ 【{role}】已存在，跳过。")
            continue

        data = generate_profile_and_relations(role)
        if not data:
            continue

        # 2. 存入标准画像表
        profile = DBJobStandardProfile(
            role_name=data["role_name"],
            description=data.get("description", ""),
            core_skills=json.dumps(data.get("core_skills", []), ensure_ascii=False),
            soft_skills=json.dumps(data.get("soft_skills", []), ensure_ascii=False),
            certifications=json.dumps(data.get("certifications", []), ensure_ascii=False)
        )
        db.add(profile)

        # 3. 存入关系图谱表 (晋升)
        for promo in data.get("promotions", []):
            rel = DBJobRelation(
                source_role=data["role_name"],
                target_role=promo["target"],
                relation_type="promotion",
                weight=promo.get("weight", 80)
            )
            db.add(rel)

        # 4. 存入关系图谱表 (平调)
        for transfer in data.get("transfers", []):
            rel = DBJobRelation(
                source_role=data["role_name"],
                target_role=transfer["target"],
                relation_type="transfer",
                weight=transfer.get("weight", 60)
            )
            db.add(rel)

        db.commit()
        print(f"🎉 【{role}】提炼完成并入库！")

    db.close()
    print("🚀 所有图谱数据造血完毕！赛题的'岗位图谱'底座已经建成！")


if __name__ == "__main__":
    main()