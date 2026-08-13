# 插件示例：plugin_example.py

# 这是一个占位的插件示例，用于说明插件应实现的接口。
# 根据目标 harness 的插件规范调整函数签名与注册方法。

class ExamplePlugin:
    def __init__(self, config=None):
        self.config = config or {}

    def setup(self):
        """插件初始化（加载资源、注册路由/命令等）"""
        print("ExamplePlugin setup with config:", self.config)

    def handle(self, input_data):
        """处理调用请求并返回结果"""
        return {"status": "ok", "echo": input_data}

# 本文件仅作模版，实际实现应符合目标 harness 的插件生命周期接口
