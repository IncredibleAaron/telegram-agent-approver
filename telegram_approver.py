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
    Telegram 移动端 Human-in-the-Loop 远程审批与交互控制器。
    支持 [✅ 批准] [❌ 拒绝] [⏸️ Hold 挂起] [💬 手机回复指令] 4 种交互模式。
    """

    def __init__(self, bot_token: str | None = None, chat_id: str | int | None = None):
        token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        raw_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if not token or not raw_chat_id:
            raise ValueError("未配置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，请检查 .env 文件。")

        self.bot_token: str = token
        self.chat_id: int = int(raw_chat_id)
        self.bot = telebot.TeleBot(self.bot_token)

    def request_approval(
        self,
        title: str,
        details: str,
        timeout_seconds: int = 300
    ) -> tuple[str, str]:
        """
        发送推送消息到 Telegram 手机端，并挂起等待用户在手机上操作。

        :param title: 审批标题
        :param details: 审批详细内容/要运行的指令/Plan
        :param timeout_seconds: 超时时间 (默认 300 秒 / 5 分钟)
        :return: 元组 (status, payload)
                 - status: "APPROVED", "REJECTED", "HOLD", "FEEDBACK", "TIMEOUT"
                 - payload: 补充说明或用户在手机上输入的文字指令
        """
        approval_result: dict[str, str | None] = {"status": None, "feedback": ""}

        # 构建 4 按钮交互卡片
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ 批准执行", callback_data="approve"),
            InlineKeyboardButton("❌ 拒绝", callback_data="reject")
        )
        markup.row(
            InlineKeyboardButton("⏸️ Hold (等回电脑)", callback_data="hold"),
            InlineKeyboardButton("💬 补充修改指令", callback_data="feedback")
        )

        message_text = (
            f"🚨 *Antigravity Agent 远程审批请求*\n\n"
            f"📌 *标题*: {title}\n"
            f"📝 *详情*:\n```\n{details}\n```\n"
            f"⏳ *超时时间*: {timeout_seconds}秒 (5分钟)"
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
            return "REJECTED", f"发送消息异常: {e}"

        waiting_for_text = {"active": False}

        # 注册内联按钮点击回调监听
        @self.bot.callback_query_handler(func=lambda call: call.message.message_id == msg.message_id)
        def handle_callback(call):
            if call.data == "approve":
                approval_result["status"] = "APPROVED"
                self.bot.answer_callback_query(call.id, "✅ 已批准！Agent 将继续执行。")
                updated_text = (
                    f"✅ *Antigravity Agent 审批已通过*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 用户已在手机端【批准】"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")

            elif call.data == "reject":
                approval_result["status"] = "REJECTED"
                self.bot.answer_callback_query(call.id, "❌ 已拒绝！")
                updated_text = (
                    f"❌ *Antigravity Agent 审批已拒绝*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 用户已在手机端【拒绝】"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")

            elif call.data == "hold":
                approval_result["status"] = "HOLD"
                self.bot.answer_callback_query(call.id, "⏸️ 已选择 Hold 挂起，等待回到电脑前处理。")
                updated_text = (
                    f"⏸️ *Antigravity Agent 任务已挂起 (Hold)*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 任务已挂起，等您回到电脑前手动接管。"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")

            elif call.data == "feedback":
                waiting_for_text["active"] = True
                self.bot.answer_callback_query(call.id, "💬 请直接在下方输入框发送您的修改指令...")
                updated_text = (
                    f"💬 *等待手机端回复修改指令...*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"👇 *请在下方聊天框直接输入您的修改建议/下一阶段指令*"
                )
                self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")

        # 注册用户文字输入监听 (当处于 feedback 状态时)
        @self.bot.message_handler(func=lambda m: m.chat.id == self.chat_id and waiting_for_text["active"])
        def handle_user_message(m):
            user_input = m.text or ""
            approval_result["status"] = "FEEDBACK"
            approval_result["feedback"] = user_input
            waiting_for_text["active"] = False

            updated_text = (
                f"📝 *已收到手机端修改指令*\n\n"
                f"📌 *原标题*: {title}\n"
                f"💬 *您的指令*: `{user_input}`\n\n"
                f"⏱️ *状态*: 指令已回传给 Antigravity Agent 进行下一步。"
            )
            self.bot.send_message(self.chat_id, updated_text, parse_mode="Markdown")

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
                    approval_result["status"] = "TIMEOUT"
                    timeout_text = (
                        f"⚠️ *Antigravity Agent 审批已超时*\n\n"
                        f"📌 *标题*: {title}\n"
                        f"📝 *详情*:\n```\n{details}\n```\n"
                        f"⏱️ *状态*: 5分钟 (300秒) 内未收到手机响应，已自动超时拒绝"
                    )
                    self.bot.edit_message_text(timeout_text, self.chat_id, msg.message_id, parse_mode="Markdown")
                    break
                time.sleep(0.5)
        finally:
            self.bot.stop_polling()

        status = approval_result["status"] or "TIMEOUT"
        feedback = approval_result["feedback"] or ""
        return status, feedback
