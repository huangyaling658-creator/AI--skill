#!/usr/bin/env python3
"""
write-to-notes.py
将今日计划写入 Apple 备忘录，保留正确的换行和纵向排列。

解决方案：
  将备忘录正文写入 UTF-8 临时文件，让 AppleScript 从文件读取，
  彻底避免命令行模式下 \\n 换行失效的问题。

用法：
    python3 write-to-notes.py "3.28 今日计划" "计划内容..."
    python3 write-to-notes.py "3.28 今日计划" "计划内容..." append
"""

import sys
import os
import subprocess
import tempfile
import datetime


# ──────────────────────────────────────────
# 工具
# ──────────────────────────────────────────

def _esc(s: str) -> str:
    """转义 AppleScript 字符串中的特殊字符（仅用于标题等短字符串）。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript_file(script: str, timeout: int = 20) -> tuple[bool, str]:
    """将 AppleScript 写入临时文件并运行，支持多行字符串和 Unicode。"""
    fd, path = tempfile.mkstemp(suffix=".applescript")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)
        result = subprocess.run(
            ["osascript", path],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "超时"
    except FileNotFoundError:
        return False, "找不到 osascript，请确认在 macOS 上运行"
    except Exception as e:
        return False, str(e)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _text_to_notes_html(content: str) -> str:
    """
    将纯文本计划转为 Apple Notes 的 HTML 格式。
    每行 → <div>...</div>，空行 → <div><br></div>
    这是 Notes 内部识别换行的唯一正确方式。
    """
    import html as html_lib
    lines = content.split("\n")
    parts = []
    for line in lines:
        s = line.strip()
        if s == "":
            parts.append("<div><br></div>")
        elif s.startswith("○"):
            parts.append(f"<div>{html_lib.escape(s[1:].strip())}</div>")
        elif s.startswith("✅"):
            parts.append(f"<div>{html_lib.escape(s[1:].strip())}</div>")
        else:
            parts.append(f"<div>{html_lib.escape(line)}</div>")
    return "\n".join(parts)


def _write_body_to_tempfile(content: str) -> str:
    """将正文 HTML 写入 UTF-8 临时文件，返回文件路径。"""
    html_content = _text_to_notes_html(content)
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html_content)
    return path


# ──────────────────────────────────────────
# 写入备忘录
# ──────────────────────────────────────────

def write_to_notes(title: str, content: str, mode: str = "new") -> bool:
    """
    将计划写入 Apple 备忘录。
    正文通过临时文件传递，确保换行和 Unicode 正确显示。
    """
    safe_title = _esc(title)
    body_path = _write_body_to_tempfile(content)

    try:
        if mode == "append":
            script = f'''
set bodyFile to POSIX file "{body_path}"
set fileRef to open for access bodyFile
set newContent to read fileRef as «class utf8»
close access fileRef

tell application "Notes"
    set targetNote to missing value
    repeat with n in notes of default account
        if name of n contains "{safe_title}" then
            set targetNote to n
            exit repeat
        end if
    end repeat
    if targetNote is missing value then
        make new note at default account with properties {{name:"{safe_title}", body:newContent}}
    else
        set body of targetNote to (body of targetNote) & newContent
    end if
end tell
'''
        else:
            script = f'''
set bodyFile to POSIX file "{body_path}"
set fileRef to open for access bodyFile
set noteBody to read fileRef as «class utf8»
close access fileRef

tell application "Notes"
    make new note at default account with properties {{name:"{safe_title}", body:noteBody}}
end tell
'''

        ok, err = _run_applescript_file(script)
        if ok:
            task_count = sum(1 for l in content.split("\n") if l.strip().startswith("○"))
            print(f"✅ 成功写入备忘录：{title}（{task_count} 条任务，纵向排列）")
        else:
            print(f"❌ AppleScript 错误：{err}")
        return ok

    finally:
        if os.path.exists(body_path):
            os.unlink(body_path)


# ──────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("用法：python3 write-to-notes.py <标题> <内容> [append]")
        sys.exit(1)

    title   = sys.argv[1]
    content = sys.argv[2]
    mode    = sys.argv[3] if len(sys.argv) > 3 else "new"

    today = datetime.date.today()
    if not any(ch.isdigit() for ch in title):
        title = f"{today.month}.{today.day} {title}"

    success = write_to_notes(title, content, mode)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
