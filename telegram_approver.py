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
    # 设置严格的网络连接超时，防止因跨境网络抖动导致 Telegram API 阻塞 20+ 秒
    telebot.apihelper.CONNECT_TIMEOUT = 3  # ty: ignore
    telebot.apihelper.READ_TIMEOUT = 5  # ty: ignore
except ImportError:
    print("错误: 缺少 pyTelegramBotAPI 依赖，请运行 `uv add pyTelegramBotAPI python-dotenv`。")
    sys.exit(1)


class TelegramApprover:
    """
    Telegram 移动端 Human-in-the-Loop 远程审批与交互控制器 (高可用抗抖动版)。
    网络超时微调至 3.5s/5.0s，秒级捕获手机回调，彻底消除 IDE 接收卡顿感。
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
        waiting_for_text = {"active": False}

        def build_initial_markup():
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("✅ 批准执行", callback_data="approve"),
                InlineKeyboardButton("❌ 拒绝", callback_data="reject")
            )
            markup.row(
                InlineKeyboardButton("⏸️ Hold (挂起/等回电脑)", callback_data="hold"),
                InlineKeyboardButton("💬 补充修改指令", callback_data="feedback")
            )
            return markup

        def build_hold_markup():
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("▶️ 恢复并批准", callback_data="approve"),
                InlineKeyboardButton("💬 补充修改指令", callback_data="feedback")
            )
            markup.row(
                InlineKeyboardButton("❌ 彻底终止", callback_data="reject")
            )
            return markup

        def build_feedback_cancel_markup():
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("↩️ 取消/返回菜单", callback_data="reset")
            )
            return markup

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
                reply_markup=build_initial_markup()
            )
        except Exception as e:  # noqa: BLE001
            print(f"[TelegramApprover] 发送 Telegram 消息失败: {e}", file=sys.stderr)
            return "REJECTED", f"发送消息异常: {e}"

        # 快速清洗过往历史 Offset，避免残留 Update 干扰
        try:
            initial_updates = self.bot.get_updates(offset=-1, timeout=1)
            last_update_id = initial_updates[-1].update_id if initial_updates else 0
        except Exception:  # noqa: BLE001
            last_update_id = 0

        start_time = time.time()
        while approval_result["status"] is None:
            if time.time() - start_time > timeout_seconds:
                approval_result["status"] = "TIMEOUT"
                timeout_text = (
                    f"⚠️ *Antigravity Agent 审批已超时*\n\n"
                    f"📌 *标题*: {title}\n"
                    f"📝 *详情*:\n```\n{details}\n```\n"
                    f"⏱️ *状态*: 5分钟 (300秒) 内未收到手机响应，已自动超时拒绝"
                )
                try:
                    self.bot.edit_message_text(timeout_text, self.chat_id, msg.message_id, parse_mode="Markdown")
                except Exception:  # noqa: BLE001, S110
                    pass
                break

            # 采用 1 秒高频增量 Polling，抗抖动且保证即时响应
            try:
                updates = self.bot.get_updates(offset=last_update_id + 1, timeout=1)
            except Exception:  # noqa: BLE001
                # 出现网络短时抖动时快速重试，不阻塞循环
                time.sleep(0.2)
                continue

            for update in updates:
                last_update_id = update.update_id

                # 处理按钮点击回调
                if (
                    update.callback_query
                    and update.callback_query.message
                    and update.callback_query.message.message_id == msg.message_id
                ):
                    call = update.callback_query
                    if call.data == "approve":
                        waiting_for_text["active"] = False
                        approval_result["status"] = "APPROVED"
                        try:
                            self.bot.answer_callback_query(call.id, "✅ 已批准！Agent 将继续执行。")
                        except Exception:  # noqa: BLE001, S110
                            pass
                        updated_text = (
                            f"✅ *Antigravity Agent 审批已通过*\n\n"
                            f"📌 *标题*: {title}\n"
                            f"📝 *详情*:\n```\n{details}\n```\n"
                            f"⏱️ *状态*: 用户已在手机端【批准】"
                        )
                        try:
                            self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")
                        except Exception:  # noqa: BLE001, S110
                            pass

                    elif call.data == "reject":
                        waiting_for_text["active"] = False
                        approval_result["status"] = "REJECTED"
                        try:
                            self.bot.answer_callback_query(call.id, "❌ 已拒绝！")
                        except Exception:  # noqa: BLE001, S110
                            pass
                        updated_text = (
                            f"❌ *Antigravity Agent 审批已拒绝*\n\n"
                            f"📌 *标题*: {title}\n"
                            f"📝 *详情*:\n```\n{details}\n```\n"
                            f"⏱️ *状态*: 用户已在手机端【拒绝】"
                        )
                        try:
                            self.bot.edit_message_text(updated_text, self.chat_id, msg.message_id, parse_mode="Markdown")
                        except Exception:  # noqa: BLE001, S110
                            pass

                    elif call.data == "hold":
                        waiting_for_text["active"] = False
                        try:
                            self.bot.answer_callback_query(call.id, "⏸️ 任务已挂起。可在手机上点击 [▶️恢复] 或等回电脑处理。")
                        except Exception:  # noqa: BLE001, S110
                            pass
                        hold_text = (
                            f"⏸️ *Antigravity Agent 任务已挂起 (Hold)*\n\n"
                            f"📌 *标题*: {title}\n"
                            f"📝 *详情*:\n```\n{details}\n```\n"
                            f"⏱️ *状态*: 任务挂起中。您可以随时回到电脑处理，或在手机上点击下方按键恢复。"
                        )
                        try:
                            self.bot.edit_message_text(
                                hold_text,
                                self.chat_id,
                                msg.message_id,
                                parse_mode="Markdown",
                                reply_markup=build_hold_markup()
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass

                    elif call.data == "feedback":
                        waiting_for_text["active"] = True
                        try:
                            self.bot.answer_callback_query(call.id, "💬 请直接在下方输入框发送您的修改指令...")
                        except Exception:  # noqa: BLE001, S110
                            pass
                        fb_text = (
                            f"💬 *等待手机端回复修改指令...*\n\n"
                            f"📌 *标题*: {title}\n"
                            f"📝 *详情*:\n```\n{details}\n```\n"
                            f"👇 *请在下方聊天框直接输入您的修改建议/下一阶段指令*\n"
                            f"*(若误触可点击下方按键取消)*"
                        )
                        try:
                            self.bot.edit_message_text(
                                fb_text,
                                self.chat_id,
                                msg.message_id,
                                parse_mode="Markdown",
                                reply_markup=build_feedback_cancel_markup()
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass

                    elif call.data == "reset":
                        waiting_for_text["active"] = False
                        try:
                            self.bot.answer_callback_query(call.id, "↩️ 已取消回复，返回主菜单。")
                        except Exception:  # noqa: BLE001, S110
                            pass
                        try:
                            self.bot.edit_message_text(
                                message_text,
                                self.chat_id,
                                msg.message_id,
                                parse_mode="Markdown",
                                reply_markup=build_initial_markup()
                            )
                        except Exception:  # noqa: BLE001, S110
                            pass

                # 处理用户发送的文本回复
                elif update.message and update.message.chat.id == self.chat_id and waiting_for_text["active"]:
                    user_input = update.message.text or ""
                    approval_result["status"] = "FEEDBACK"
                    approval_result["feedback"] = user_input
                    waiting_for_text["active"] = False

                    updated_text = (
                        f"📝 *已收到手机端修改指令*\n\n"
                        f"📌 *原标题*: {title}\n"
                        f"💬 *您的指令*: `{user_input}`\n\n"
                        f"⏱️ *状态*: 指令已回传给 Antigravity Agent 进行下一步。"
                    )
                    try:
                        self.bot.send_message(self.chat_id, updated_text, parse_mode="Markdown")
                    except Exception:  # noqa: BLE001, S110
                        pass

            time.sleep(0.1)

        status = approval_result["status"] or "TIMEOUT"
        feedback = approval_result["feedback"] or ""
        return status, feedback
