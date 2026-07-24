import json
import logging
import sys

from telegram_approver import TelegramApprover

# 配置日志，避免在 stdio 管道中打印非 JSON 内容
logger = logging.getLogger("telegram_approver_mcp")
logger.setLevel(logging.ERROR)
handler = logging.StreamHandler(sys.stderr)
logger.addHandler(handler)

TOOLS = [
    {
        "name": "request_mobile_approval",
        "description": "向用户的手机 Telegram 发送交互式审批请求卡片（带【批准】、【拒绝】、【Hold 挂起】及【补充修改指令】按键），并挂起等待用户在手机上选择或输入。适用于运行高风险指令、文件修改或 Plan 审阅时使用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "审批标题，简要说明申请事项（例如：'运行高风险指令'、'删除临时文件'）"
                },
                "details": {
                    "type": "string",
                    "description": "审批详细内容（例如：要运行的具体命令、修改的 Plan 文件内容或 Diff 摘要）"
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "手机端响应超时时间（单位：秒，默认 300 秒 / 5 分钟）",
                    "default": 300
                }
            },
            "required": ["title", "details"]
        }
    }
]


def handle_request(request: dict) -> dict | None:
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "telegram-agent-approver-mcp",
                    "version": "1.2.0"
                }
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }

    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "request_mobile_approval":
            title = arguments.get("title", "MCP 审批请求")
            details = arguments.get("details", "")
            timeout_seconds = int(arguments.get("timeout_seconds", 300))

            try:
                approver = TelegramApprover()
                status, feedback = approver.request_approval(
                    title=title,
                    details=details,
                    timeout_seconds=timeout_seconds
                )

                if status == "APPROVED":
                    result_text = "✅ 用户已在手机 Telegram 端【批准】此操作。请继续按计划执行。"
                    is_error = False
                elif status == "HOLD":
                    result_text = (
                        "🛑 [强制暂停指令] 用户已在手机端选择了【Hold (等回电脑)】。\n"
                        "⚠️ 严禁行为：你绝对不能再调用任何工具，不能尝试自动修复，不能执行命令，也不能修改文件！\n"
                        "📌 正确操作：你必须立刻终止调用工具，向用户输出一句 short message 说明“任务已按手机 Hold 要求暂停，等待用户回到电脑前手动接管”，然后结束当前 Turn。"
                    )
                    is_error = False
                elif status == "FEEDBACK":
                    result_text = (
                        f"💬 用户在手机 Telegram 端提交了下一阶段指示: '{feedback}'。\n"
                        f"📌 请严格遵循用户的这条手机反馈指示进行下一步操作。"
                    )
                    is_error = False
                elif status == "REJECTED":
                    result_text = (
                        "🛑 [拒绝指令] 用户已在手机 Telegram 端【拒绝】此操作。\n"
                        "⚠️ 请放弃执行该操作，不要强制重试。"
                    )
                    is_error = True
                else:  # TIMEOUT
                    result_text = (
                        f"⚠️ 审批在 {timeout_seconds} 秒 (5分钟) 内未收到手机端响应，已自动超时拒绝。"
                    )
                    is_error = True

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ],
                        "isError": is_error
                    }
                }
            except Exception as e:  # noqa: BLE001
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"❌ 手机端审批调用异常: {e}"
                            }
                        ],
                        "isError": True
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"未知的 Tool 名称: {tool_name}"
                }
            }

    elif req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"未支持的方法: {method}"
            }
        }

    return None


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:  # noqa: BLE001
            logger.error(f"处理请求失败: {e}")


if __name__ == "__main__":
    main()
