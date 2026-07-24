import argparse
import io
import sys

from telegram_approver import TelegramApprover

# UTF-8 兼容支持 (防止 Windows 控制台 GBK 编码报错)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Mobile Approval CLI - 跨端命令行远程审批工具"
    )
    parser.add_argument("title", type=str, help="审批标题")
    parser.add_argument("details", type=str, help="审批详情内容或要运行的指令")
    parser.add_argument(
        "--timeout", "-t", type=int, default=300, help="超时时间（单位：秒，默认 300）"
    )

    args = parser.parse_args()

    try:
        approver = TelegramApprover()
    except Exception as e:  # noqa: BLE001
        print(f"❌ 初始化 Telegram 审批服务失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"📱 审批消息已发送至手机 Telegram [{args.title}]")
    print(f"⌛ 正在等待手机端操作 (限时 {args.timeout} 秒)...")

    approved = approver.request_approval(
        title=args.title,
        details=args.details,
        timeout_seconds=args.timeout
    )

    if approved:
        print("🎉 用户已在手机端【批准】执行！")
        sys.exit(0)
    else:
        print("🛑 用户已在手机端【拒绝】或响应超时！")
        sys.exit(1)


if __name__ == "__main__":
    main()
