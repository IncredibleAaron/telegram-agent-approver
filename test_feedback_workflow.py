import io
import sys

from telegram_approver import TelegramApprover

# UTF-8 控制台输出支持
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def run_simulated_agent_workflow():
    print("=" * 70)
    print(" 🤖 Agent 完整多轮交互测试工作流 (模拟实际开发中的【修改指令回传】)")
    print("=" * 70)

    approver = TelegramApprover()

    # -------------------------------------------------------------
    # 阶段 1：Agent 提出初始 Plan (等待用户审核)
    # -------------------------------------------------------------
    print("\n[Agent 阶段 1] 提出初始方案：删除 hello.py 并重构 main.py")
    print("📱 发送审批卡片至 Telegram...")
    print("👇 **请在手机上点击 [💬 补充修改指令]，并输入：【保留 hello.py，只修改 main.py】**\n")

    status, feedback = approver.request_approval(
        title="[阶段1] 重构方案审批",
        details="Agent 计划：\n1. 删除 hello.py\n2. 重构 main.py 逻辑\n\n请确认或回复修改指令。",
        timeout_seconds=300
    )

    print(f"--> 阶段 1 返回状态: {status}")

    if status == "FEEDBACK":
        print(f"🎉 成功接收到手机端回传修改指令: '{feedback}'")
        print("\n🤖 [Agent 正在依据手机端指令调整方案...]")
        revised_plan = f"依据您的手机指令『{feedback}』，新方案为：保留 hello.py，仅重构 main.py。"
    elif status == "APPROVED":
        print("✅ 用户直接批准了初始方案。")
        revised_plan = "保留初始方案。"
    elif status == "HOLD":
        print("⏸️ 用户选择了 Hold 挂起，等待回到电脑前处理。")
        return
    else:
        print("🛑 方案被拒绝或超时。")
        return

    # -------------------------------------------------------------
    # 阶段 2：Agent 根据手机指令调整后，再次发起最终确认
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print(f"[Agent 阶段 2] 提交调整后的最终方案:\n{revised_plan}")
    print("📱 发送二次确认卡片至 Telegram...")
    print("👇 **请在手机上点击 [✅ 批准执行] 完成全流程测试**\n")

    final_status, _ = approver.request_approval(
        title="[阶段2] 调整后方案最终确认",
        details=f"调整后的方案：\n{revised_plan}\n\n确认无误请点击批准。",
        timeout_seconds=300
    )

    print("-" * 70)
    if final_status == "APPROVED":
        print("🏆 多轮交互测试完美闭环！Agent 依据手机指令调整并最终获得批准！")
    else:
        print(f"阶段 2 结果: {final_status}")
    print("=" * 70)


if __name__ == "__main__":
    run_simulated_agent_workflow()
