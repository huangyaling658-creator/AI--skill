#!/usr/bin/env python3
"""
write-to-notes.py
将今日计划写入 Apple 备忘录（仅限 macOS），支持原生 Checklist 打勾格式。

用法：
    python3 write-to-notes.py "3.28 今日计划" "计划内容..."
    python3 write-to-notes.py "3.28 今日计划" "计划内容..." append

参数：
    argv[1] - 备忘录标题
    argv[2] - 备忘录正文（纯文本，含 ○/✅ 标记）
    argv[3] - (可选) "append" 追加模式，默认新建

格式映射：
    ○ 任务   → Apple 备忘录原生 Checklist（未完成，可点击打勾）
    ✅ 任务  → Apple 备忘录原生 Checklist（已完成，带删除线）
    【想法】 → 加粗段落
    其他文字 → 普通段落
    空行     → 段落间距
"""

import sys
import subprocess
import datetime
import html as html_lib


# ──────────────────────────────────────────
# 文本 → Apple Notes HTML
# ──────────────────────────────────────────

def plan_text_to_html(content: str) -> str:
    """
    将计划纯文本转换为 Apple Notes 可识别的 HTML。
    ○ 行 → <ul class="Apple-checklist"> unchecked item
    ✅ 行 → <ul class="Apple-checklist"> checked item（带删除线）
    其他  → <p> 段落
    """
    lines = content.split("\n")
    parts = ["<div>"]
    in_checklist = False

    for line in lines:
        s = line.strip()

        # 空行
        if not s:
            if in_checklist:
                parts.append("</ul>")
                in_checklist = False
            parts.append("<p><br></p>")
            continue

        # 未完成任务 ○
        if s.startswith("○"):
            if not in_checklist:
                parts.append('<ul class="Apple-checklist">')
                in_checklist = True
            task = html_lib.escape(s[1:].strip())
            parts.append(f"<li>{task}</li>")

        # 已完成任务 ✅
        elif s.startswith("✅"):
            if not in_checklist:
                parts.append('<ul class="Apple-checklist">')
                in_checklist = True
            task = html_lib.escape(s[1:].strip())
            # checked 状态：Apple Notes 用 checked attribute + 删除线表示
            parts.append(f'<li data-checked="true"><s>{task}</s></li>')

        # 普通文本（碎碎念、想法、日期行等）
        else:
            if in_checklist:
                parts.append("</ul>")
                in_checklist = False
            text = html_lib.escape(s)
            if s.startswith("【想法】") or s.startswith("[想法]"):
                parts.append(f"<p><b>{text}</b></p>")
            else:
                parts.append(f"<p>{text}</p>")

    if in_checklist:
        parts.append("</ul>")

    parts.append("</div>")
    return "\n".join(parts)


# ──────────────────────────────────────────
# 写入 Apple 备忘录
# ──────────────────────────────────────────

def _escape_for_applescript(s: str) -> str:
    """转义 AppleScript 字符串中的特殊字符。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_to_notes(title: str, content: str, mode: str = "new") -> bool:
    """
    将计划写入 Apple 备忘录，任务行自动转为原生 Checklist。

    Args:
        title:   备忘录标题
        content: 计划纯文本（含 ○/✅ 标记）
        mode:    "new" 新建 | "append" 追加

    Returns:
        True 成功，False 失败
    """
    html_body = plan_text_to_html(content)
    safe_title = _escape_for_applescript(title)
    safe_html  = _escape_for_applescript(html_body)

    if mode == "append":
        script = f'''
tell application "Notes"
    set targetNote to missing value
    repeat with n in notes of default account
        if name of n contains "{safe_title}" then
            set targetNote to n
            exit repeat
        end if
    end repeat
    if targetNote is missing value then
        make new note at default account with properties {{name:"{safe_title}", body:"{safe_html}"}}
    else
        set body of targetNote to (body of targetNote) & "{safe_html}"
    end if
end tell
'''
    else:
        script = f'''
tell application "Notes"
    make new note at default account with properties {{name:"{safe_title}", body:"{safe_html}"}}
end tell
'''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            print(f"✅ 成功写入备忘录：{title}（含可打勾 Checklist）")
            return True
        else:
            print(f"❌ AppleScript 错误：{result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ 超时：Apple 备忘录响应太慢")
        return False
    except FileNotFoundError:
        print("❌ 找不到 osascript，请确认你在 macOS 上运行")
        return False
    except Exception as e:
        print(f"❌ 未知错误：{e}")
        return False


# ──────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("用法：python3 write-to-notes.py <标题> <内容> [append]")
        print("示例：python3 write-to-notes.py '3.28 今日计划' '3.28\\n昨晚睡得不错\\n○ 做AI音乐 11-12\\n✅ 吃饭 12-13'")
        sys.exit(1)

    title   = sys.argv[1]
    content = sys.argv[2]
    mode    = sys.argv[3] if len(sys.argv) > 3 else "new"

    # 标题没有数字时自动加今日日期
    today = datetime.date.today()
    if not any(ch.isdigit() for ch in title):
        title = f"{today.month}.{today.day} {title}"

    success = write_to_notes(title, content, mode)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
