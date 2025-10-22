"""
测试运行脚本 - 运行所有单元测试

使用方法：
    python tests/run_tests.py              # 运行所有测试
    python tests/run_tests.py -v           # 详细输出
    python tests/run_tests.py test_mqtt    # 运行特定测试
"""
import sys
import unittest
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_all_tests(verbosity=2, pattern='test_*.py'):
    """运行所有测试"""
    # 创建测试加载器
    loader = unittest.TestLoader()

    # 加载测试目录中的所有测试
    tests_dir = Path(__file__).parent
    suite = loader.discover(str(tests_dir), pattern=pattern)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return result.wasSuccessful()


def print_test_summary():
    """打印测试摘要"""
    print("\n" + "=" * 70)
    print("DJI SDK 单元测试套件")
    print("=" * 70)
    print("\n测试模块：")
    print("  - test_mqtt_client.py    : MQTTClient 核心功能")
    print("  - test_service_caller.py : ServiceCaller 服务调用")
    print("  - test_commands.py       : 业务服务层 (commands)")
    print("  - test_heartbeat.py      : 心跳服务")
    print("\n运行中...\n")


if __name__ == '__main__':
    print_test_summary()

    # 解析命令行参数
    verbosity = 2
    pattern = 'test_*.py'

    if len(sys.argv) > 1:
        if '-v' in sys.argv or '--verbose' in sys.argv:
            verbosity = 2
        elif '-q' in sys.argv or '--quiet' in sys.argv:
            verbosity = 0
        else:
            # 如果提供了测试模块名
            pattern = f"{sys.argv[1]}*.py"

    # 运行测试
    success = run_all_tests(verbosity=verbosity, pattern=pattern)

    # 退出码
    sys.exit(0 if success else 1)
