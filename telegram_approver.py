import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# 加载当前或同级目录下的 .env 文件
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

try:
    import telebot
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    print("错误: 缺少 pyTelegramBotAPI 依赖，请运行 `uv add pyTelegramBotAPI python-dotenv`。")
    sys.exit(1)


class TelegramApprover:
    """
    Telegram 移动端 Human-in-the-Loop 远程审批类。
    利用 Telegram Bot 内联按钮卡片与长轮询 (Long Polling)，实现安全的零公网跨端确认。
    """

    def __init__(self, bot_token: str | None = None, chat_id: str | int | None = None):
        token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        raw_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if not token or not raw_chat_id:
            raise ValueError("未配置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，请检查 .env 文件。")

        self.bot_token: str = token
        self.chat_id: int = int(raw_chat_id)
        self.bot = telebot.TeleBot(self.bot_token)

    def request_approval(self, title: str, details: str, timeout_seconds: int = 300) -> bool:
        """
        发送推送消息到 Telegram 手机端，并挂起等待用户在手机上选择 [✅ 批准] 或 [❌ 拒绝]。

        :param title: 审批标题 (例如 "高风险命令执行确认")
        :param details: 审批详细内容 (例如 "git push origin main --force")
        :param timeout_seconds: 超时时间 (单位：秒，默认 300 秒)
        :return: True 表示用户在手机上点击了批准，False 表示拒绝或超时
        """
        approval_result = {"status": None}

        # 构建 Telegram 消息卡片按键
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ 批准执行", callback_data="approve"),
            InlineKeyboardButton("❌ 拒绝", callback_data="reject")
        )

        message_text = (
            f"🚨 *Antigravity IDE / Agent 审批请求*\n\n"
            f"📌 *标题*: {title}\n"
            f"📝 *详情*:\n```\n{details}\n```\n"
            f"⏳ *超时时间*: {timeout_seconds}秒"
        )

        try:
            msg = self.bot.send_message(
                self.chat_id,
                message_text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:  # noqa: BLE001
            print(f"[TelegramApprover] 发送 Telegram 消息失败: {e}", file=sys.stderr)
            return False

        # 注册内联按钮点击回调监听
        @self.bot.callback_query_handler(func=lambda call: call.message.message_id == msg.message_id)
        def handle_callback(call):
            if call.data == "approve":
                approval_result["status"] = True
                self.bot.answer_callback_query(call.id, "✅ 已批准！Agent 将继续执行。")
                updated_text = (
                    f"✅ *Antigravity Agent 审批已通过*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 用户已在手机端【批准】"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")
            else:
                approval_result["status"] = False
                self.bot.answer_callback_query(call.id, "❌ 已拒绝！")
                updated_text = (
                    f"❌ *Antigravity Agent 审批已拒绝*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 用户已在手机端【拒绝】"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")

        # 启动后台守护线程长轮询
        import threading
        polling_thread = threading.Thread(
            target=self.bot.infinity_polling,
            kwargs={"skip_pending": True},
            daemon=True
        )
        polling_thread.start()

        start_time = time.time()
        try:
            while approval_result["status"] is None:
                if time.time() - start_time > timeout_seconds:
                    approval_result["status"] = False
                    timeout_text = (
                        f"⚠️ *Antigravity Agent 审批已超时*\n\n"
                        f"📌 *标题*: {title}\n"
                        f"📝 *详情*:\n```\n{details}\n```\n"
                        f"⏱️ *状态*: {timeout_seconds}秒内未收到手机响应，已自动拒绝"
                    )
                    self.bot.edit_message_text(timeout_text, self.chat_id, msg.message_id, parse_mode="Markdown")
                    break
                time.sleep(0.5)
        finally:
            self.bot.stop_polling()

        return bool(approval_result["status"])
