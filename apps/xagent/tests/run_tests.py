#!/usr/bin/env python3
"""测试运行脚本 - 快速运行所有测试"""

import sys
import subprocess
from pathlib import Path


def run_tests(test_type="all", verbose=True):
    """运行测试

    Args:
        test_type: 测试类型 (all, statistics, storage, api)
        verbose: 是否显示详细输出
    """
    # 切换到测试目录
    test_dir = Path(__file__).parent

    # 构建测试命令
    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    # 根据测试类型选择测试文件
    if test_type == "all":
        cmd.append("tests/")
    elif test_type == "statistics":
        cmd.append("tests/statistics/test_statistics_manager_extended.py")
    elif test_type == "storage":
        cmd.append("tests/storage/test_storage_extended.py")
    elif test_type == "api":
        cmd.append("tests/api/test_system_api.py")
    else:
        print(f"❌ 未知的测试类型: {test_type}")
        return 1

    # 添加覆盖率选项
    cmd.extend([
        "--cov=xagent.xcore.statistics",
        "--cov=xagent.xcore.storage",
        "--cov=xagent.xcore.api.routers.system",
        "--cov-report=term-missing",
        "--cov-report=html"
    ])

    print(f"🚀 运行测试: {' '.join(cmd)}")
    print(f"📁 工作目录: {test_dir}")
    print("-" * 80)

    # 运行测试
    result = subprocess.run(cmd, cwd=test_dir)

    if result.returncode == 0:
        print("\n" + "=" * 80)
        print("✅ 所有测试通过！")
        print("=" * 80)
        print("\n📊 测试覆盖率报告已生成:")
        print(f"   HTML报告: {test_dir / 'htmlcov' / 'index.html'}")
        print("\n💡 提示:")
        print("   - 查看详细报告: open htmlcov/index.html")
        print("   - 运行特定测试: python run_tests.py [statistics|storage|api]")
        print("   - 运行所有测试: python run_tests.py all")
    else:
        print("\n" + "=" * 80)
        print("❌ 测试失败！")
        print("=" * 80)
        print("\n💡 故障排查:")
        print("   1. 检查测试输出中的错误信息")
        print("   2. 确保所有依赖已安装: pip install pytest pytest-asyncio pytest-cov")
        print("   3. 检查代码是否有语法错误")
        print("   4. 查看测试日志获取详细信息")

    return result.returncode


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="运行后端 API 测试")
    parser.add_argument(
        "type",
        nargs="?",
        default="all",
        choices=["all", "statistics", "storage", "api"],
        help="测试类型 (默认: all)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="简洁输出"
    )

    args = parser.parse_args()

    return run_tests(test_type=args.type, verbose=not args.quiet)


if __name__ == "__main__":
    sys.exit(main())
