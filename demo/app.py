import os
import re

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import requests


def fix_latex_newlines(content: str) -> str:
    r"""确保 LaTeX 矩阵换行符 \\ 在 JSON + Markdown 管线中不被吃掉。

    AI 返回的 LaTeX 矩阵中 \\ 是换行符（2 个反斜杠）。
    经过 Flask jsonify() → JS JSON.parse() 已经吃了一层转义，
    如果再被 marked.js 处理又会吃掉一层。
    这里在所有 \\ 的后面补两个反斜杠，变 \\ 为 \\\\（实际字节翻倍），
    这样即使管线中损失一层转义，KaTeX 仍能收到正确的 \\。
    """
    # 匹配 LaTeX 换行符：\\ 后面可选空格/制表符然后换行，或 \\ 后直接跟非字母字符
    # 替换为 \\\\（4 个反斜杠）
    content = content.replace('\\\\', '\\\\\\\\')
    return content

load_dotenv()

app = Flask(__name__)

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """你是一个专业的出题助手。请根据用户的要求生成试卷。

要求：
1. 使用 Markdown 格式输出，结构清晰。
2. 每道题包含：题号、题型（单选题/多选题/填空题/判断题/简答题等）、题目内容、选项（如有）、以及 **正确答案**。
3. 如果用户指定了题目数量和难度，请严格遵守。
4. 在试卷末尾附上答案汇总。

格式示例：
# 试卷标题

## 一、单选题
**1.** 题目内容...
A. 选项A
B. 选项B
C. 选项C
D. 选项D
> 正确答案：B

...（后续题目）"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    prompt = data.get("prompt", "").strip() if data else ""

    if not prompt:
        return jsonify({"error": "请输入出题要求"}), 400

    if not LLM_API_KEY:
        return jsonify({"error": "未配置 LLM_API_KEY，请将 .env.example 复制为 .env 并填入你的 API Key"}), 500

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            },
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        content = fix_latex_newlines(content)
        return jsonify({"content": content})

    except requests.exceptions.Timeout:
        return jsonify({"error": "AI 响应超时（120 秒），请稍后重试"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API 请求失败：{e}"}), 500
    except (KeyError, IndexError, TypeError) as e:
        return jsonify({"error": f"API 返回格式异常：{e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
