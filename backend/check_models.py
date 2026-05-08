from zhipuai import ZhipuAI

client = ZhipuAI(api_key="a6dc25c328bd4bd2989ffdbbba7e5d5a.6zfJxUlw9urOXLGg")

# 获取当前 Key 权限下的模型列表
try:
    models = client.models.list()
    for model in models.data:
        print(f"可用模型: {model.id}")
except Exception as e:
    print(f"获取失败: {e}")