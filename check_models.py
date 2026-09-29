"""检查当前环境变量中的智谱模型权限，不在源码中保存凭据。"""

import os

from dotenv import load_dotenv
from zhipuai import ZhipuAI

load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    raise RuntimeError("请先在 .env 中配置 ZHIPUAI_API_KEY")

client = ZhipuAI(api_key=api_key)

# 获取当前 Key 权限下的模型列表
try:
    models = client.models.list()
    for model in models.data:
        print(f"可用模型: {model.id}")
except Exception as e:
    print(f"获取失败: {e}")
