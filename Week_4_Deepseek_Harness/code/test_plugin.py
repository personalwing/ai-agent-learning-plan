# 插件测试示例

from plugin_example import ExamplePlugin

def test_plugin():
    p = ExamplePlugin({"name": "test"})
    p.setup()
    res = p.handle({"q": "hello"})
    assert res.get("status") == "ok"
    print("插件测试通过：", res)

if __name__ == '__main__':
    test_plugin()
