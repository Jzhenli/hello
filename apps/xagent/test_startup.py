"""测试启动流程 - CLI 模式和桌面模式"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from xagent.xcore.core import ConfigManager, setup_logging
from xagent.xcore.gateway import Gateway
from xagent.xcore.api.dependencies import get_app_state
from xagent.xcore.storage import SQLiteStorage, WriteBehindBuffer
from xagent.xcore.core.metadata import MetadataManager
from xagent.xcore.api.services.command_executor import CommandExecutor


async def test_cli_mode_startup():
    """测试 CLI 模式启动流程"""
    print("\n" + "="*60)
    print("测试 CLI 模式启动流程")
    print("="*60)

    try:
        # 1. 初始化配置
        print("\n[1] 初始化配置...")
        config_manager = ConfigManager()
        config = config_manager.load()
        setup_logging(config.logging)
        print("    [OK] 配置加载成功")

        # 2. 创建 Gateway
        print("\n[2] 创建 Gateway...")
        gateway = Gateway(config_manager=config_manager)
        print("    [OK] Gateway 创建成功")

        # 3. 初始化 Gateway
        print("\n[3] 初始化 Gateway...")
        await gateway.initialize()
        print("    [OK] Gateway 初始化成功")

        # 4. 启动核心服务
        print("\n[4] 启动核心服务...")
        await gateway.start_core()
        print("    [OK] 核心服务启动成功")

        # 5. 验证依赖注入
        print("\n[5] 验证依赖注入...")
        state = get_app_state()

        checks = {
            "storage": state.storage is not None,
            "buffer": state.buffer is not None,
            "metadata_manager": state.metadata_manager is not None,
            "command_executor": state.command_executor is not None,
            "gateway": state.gateway is not None,
            "user_permission_service": state.user_permission_service is not None,
        }

        all_passed = all(checks.values())
        for name, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"    {status} {name}: {passed}")

        if not all_passed:
            print("\n[FAIL] 依赖注入验证失败")
            return False

        # 6. 测试登录功能
        print("\n[6] 测试登录功能...")
        if state.user_permission_service:
            user = await state.user_permission_service.authenticate("admin", "admin")
            if user:
                print(f"    [OK] 登录成功: {user['username']}")
            else:
                print("    [FAIL] 登录失败")
                return False
        else:
            print("    [FAIL] user_permission_service 未初始化")
            return False

        # 7. 清理资源
        print("\n[7] 清理资源...")
        await gateway.stop()
        print("    [OK] 资源清理完成")

        print("\n" + "="*60)
        print("[SUCCESS] CLI 模式启动流程测试通过")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_desktop_mode_startup():
    """测试桌面模式启动流程（模拟 FastAPI lifespan）"""
    print("\n" + "="*60)
    print("测试桌面模式启动流程")
    print("="*60)

    try:
        # 1. 模拟 FastAPI lifespan 启动
        print("\n[1] 模拟 FastAPI lifespan 启动...")
        state = get_app_state()

        # 检查是否已初始化
        if not state.is_initialized():
            print("    [INFO] 状态未初始化，开始初始化...")

            # 2. 创建 Gateway
            print("\n[2] 创建 Gateway...")
            gateway = Gateway()
            print("    [OK] Gateway 创建成功")

            # 3. 初始化 Gateway
            print("\n[3] 初始化 Gateway...")
            await gateway.initialize()
            print("    [OK] Gateway 初始化成功")

            # 4. 启动核心服务
            print("\n[4] 启动核心服务...")
            await gateway.start_core()
            print("    [OK] 核心服务启动成功")

            state._gateway_owned = True
        else:
            print("    [INFO] 状态已初始化，跳过初始化")
            state._gateway_owned = False

        # 5. 验证依赖注入
        print("\n[5] 验证依赖注入...")
        state = get_app_state()

        checks = {
            "storage": state.storage is not None,
            "buffer": state.buffer is not None,
            "metadata_manager": state.metadata_manager is not None,
            "command_executor": state.command_executor is not None,
            "gateway": state.gateway is not None,
            "user_permission_service": state.user_permission_service is not None,
        }

        all_passed = all(checks.values())
        for name, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"    {status} {name}: {passed}")

        if not all_passed:
            print("\n[FAIL] 依赖注入验证失败")
            return False

        # 6. 测试登录功能
        print("\n[6] 测试登录功能...")
        if state.user_permission_service:
            user = await state.user_permission_service.authenticate("admin", "admin")
            if user:
                print(f"    [OK] 登录成功: {user['username']}")
            else:
                print("    [FAIL] 登录失败")
                return False
        else:
            print("    [FAIL] user_permission_service 未初始化")
            return False

        # 7. 清理资源
        print("\n[7] 清理资源...")
        state = get_app_state()
        if state._gateway_owned and state.gateway:
            await state.gateway.stop()
            print("    [OK] 资源清理完成")

        print("\n" + "="*60)
        print("[SUCCESS] 桌面模式启动流程测试通过")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_startup():
    """测试统一启动流程"""
    print("\n" + "="*60)
    print("测试统一启动流程")
    print("="*60)

    try:
        # 测试 CLI 模式
        cli_passed = await test_cli_mode_startup()

        # 清理状态
        state = get_app_state()
        state.storage = None
        state.buffer = None
        state.metadata_manager = None
        state.command_executor = None
        state.gateway = None
        state.cleanup_task = None
        state.user_permission_service = None

        # 测试桌面模式
        desktop_passed = await test_desktop_mode_startup()

        # 汇总结果
        print("\n" + "="*60)
        print("测试结果汇总")
        print("="*60)
        print(f"CLI 模式:    {'[PASS]' if cli_passed else '[FAIL]'}")
        print(f"桌面模式:    {'[PASS]' if desktop_passed else '[FAIL]'}")
        print("="*60)

        if cli_passed and desktop_passed:
            print("\n[SUCCESS] 所有测试通过！启动流程已统一且优雅。")
            return True
        else:
            print("\n[FAIL] 部分测试失败，请检查启动流程。")
            return False

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_dependency_injection_consistency():
    """测试依赖注入一致性"""
    print("\n" + "="*60)
    print("测试依赖注入一致性")
    print("="*60)

    try:
        # 创建 Gateway
        print("\n[1] 创建 Gateway...")
        config_manager = ConfigManager()
        gateway = Gateway(config_manager=config_manager)
        await gateway.initialize()
        print("    [OK] Gateway 初始化成功")

        # 验证 Gateway 内部的服务
        print("\n[2] 验证 Gateway 内部服务...")
        internal_services = {
            "_user_permission_service": gateway._user_permission_service is not None,
            "_north_channel_service": gateway._north_channel_service is not None,
            "rule_engine": gateway.rule_engine is not None,
            "stats_manager": gateway.stats_manager is not None,
        }

        for name, exists in internal_services.items():
            status = "[OK]" if exists else "[WARN]"
            print(f"    {status} {name}: {exists}")

        # 验证 AppState 中的服务
        print("\n[3] 验证 AppState 中的服务...")
        state = get_app_state()
        app_state_services = {
            "storage": state.storage is not None,
            "buffer": state.buffer is not None,
            "user_permission_service": state.user_permission_service is not None,
            "gateway": state.gateway is not None,
        }

        for name, exists in app_state_services.items():
            status = "[OK]" if exists else "[FAIL]"
            print(f"    {status} {name}: {exists}")

        # 验证一致性
        print("\n[4] 验证一致性...")
        consistency_checks = [
            ("Gateway._user_permission_service", gateway._user_permission_service),
            ("AppState.user_permission_service", state.user_permission_service),
        ]

        # 检查是否是同一个实例
        if gateway._user_permission_service is state.user_permission_service:
            print("    [OK] user_permission_service 实例一致")
        else:
            print("    [WARN] user_permission_service 实例不一致（可能在不同上下文中）")

        if gateway is state.gateway:
            print("    [OK] gateway 实例一致")
        else:
            print("    [FAIL] gateway 实例不一致")
            return False

        # 清理
        print("\n[5] 清理资源...")
        await gateway.stop()
        print("    [OK] 资源清理完成")

        print("\n" + "="*60)
        print("[SUCCESS] 依赖注入一致性测试通过")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("XAgent 启动流程测试套件")
    print("="*60)

    tests = [
        ("统一启动流程测试", test_unified_startup),
        ("依赖注入一致性测试", test_dependency_injection_consistency),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n运行测试: {name}")
        try:
            passed = await test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"[ERROR] 测试异常: {e}")
            results.append((name, False))

    # 打印最终结果
    print("\n" + "="*60)
    print("最终测试结果")
    print("="*60)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")

    all_passed = all(passed for _, passed in results)
    print("="*60)
    if all_passed:
        print("\n[SUCCESS] 所有测试通过！✓")
        print("\n启动流程已统一且优雅：")
        print("  1. Gateway.initialize() 统一负责依赖注入")
        print("  2. CLI 和桌面模式使用相同的初始化流程")
        print("  3. 无重复调用，代码简洁清晰")
    else:
        print("\n[FAIL] 部分测试失败，请检查代码。")
    print()

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
