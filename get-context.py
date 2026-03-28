#!/usr/bin/env python3
"""
get-context.py
自动获取两类上下文，供 daily-plan skill 生成计划时使用：
  1. 今日 Apple 日历事件
  2. 昨日备忘录中的未完成项（○ 开头的行）

用法：
    python3 get-context.py
    python3 get-context.py --date 2026-03-28   # 指定日期（调试用）

输出：JSON，格式如下：
{
  "calendar_events": [
    {"time": "14:00-15:00", "title": "产品评审会"}
  ],
  "unfinished_yesterday": [
    "产品工作台（今天因为opus4.6挂机，没用，明早起来第一个干这个）"
  ],
  "yesterday_note_found": true
}
"""

import sys
import json
import subprocess
import datetime
import argparse


def run_applescript(script: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_calendar_events(date: datetime.date) -> list[dict]:
    """
    从 Apple 日历读取指定日期的全部事件。
    返回 [{"time": "HH:MM-HH:MM", "title": "..."}, ...]
    全天事件 time 为 "全天"。
    """
    date_str = date.strftime("%Y-%m-%d")

    script = f'''
set targetDate to date "{date.strftime("%B %d, %Y")}"
set startOfDay to targetDate
set startOfDay to startOfDay - (time of startOfDay)
set endOfDay to startOfDay + 86399

set eventList to {{}}
tell application "Calendar"
    repeat with cal in calendars
        set calEvents to (every event of cal whose start date >= startOfDay and start date <= endOfDay)
        repeat with e in calEvents
            set eTitle to summary of e
            set eStart to start date of e
            set eEnd to end date of e
            set allDay to allday event of e
            if allDay then
                set timeStr to "全天"
            else
                set startHour to hours of eStart as string
                set startMin to minutes of eStart as string
                if (minutes of eStart) < 10 then set startMin to "0" & startMin
                set endHour to hours of eEnd as string
                set endMin to minutes of eEnd as string
                if (minutes of eEnd) < 10 then set endMin to "0" & endMin
                set timeStr to startHour & ":" & startMin & "-" & endHour & ":" & endMin
            end if
            set end of eventList to (timeStr & "|" & eTitle)
        end repeat
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return eventList as string
'''

    ok, output = run_applescript(script)
    if not ok or not output:
        return []

    events = []
    for line in output.splitlines():
        line = line.strip()
        if "|" in line:
            time_part, title_part = line.split("|", 1)
            events.append({"time": time_part.strip(), "title": title_part.strip()})
    return events


def get_yesterday_unfinished(yesterday: datetime.date) -> tuple[bool, list[str]]:
    """
    从 Apple 备忘录查找昨日计划笔记，提取所有以 ○ 开头的未完成项。
    笔记标题格式：M.D 今日计划（如 "3.27 今日计划"）
    返回 (note_found, [未完成任务描述, ...])
    """
    note_title = f"{yesterday.month}.{yesterday.day} 今日计划"

    script = f'''
tell application "Notes"
    set targetNote to missing value
    repeat with n in notes of default account
        if name of n contains "{note_title}" then
            set targetNote to n
            exit repeat
        end if
    end repeat
    if targetNote is missing value then
        return "NOT_FOUND"
    else
        return body of targetNote
    end if
end tell
'''

    ok, output = run_applescript(script)
    if not ok or output == "NOT_FOUND" or not output:
        return False, []

    unfinished = []
    for line in output.splitlines():
        stripped = line.strip()
        # 匹配 ○ 开头（未完成项）
        if stripped.startswith("○"):
            # 去掉开头的 ○ 和空格，保留任务描述
            task = stripped[1:].strip()
            if task:
                unfinished.append(task)

    return True, unfinished


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="指定今日日期 YYYY-MM-DD（默认今天）")
    args = parser.parse_args()

    if args.date:
        today = datetime.date.fromisoformat(args.date)
    else:
        today = datetime.date.today()

    yesterday = today - datetime.timedelta(days=1)

    calendar_events = get_calendar_events(today)
    note_found, unfinished = get_yesterday_unfinished(yesterday)

    result = {
        "today": today.strftime("%Y-%m-%d"),
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "calendar_events": calendar_events,
        "unfinished_yesterday": unfinished,
        "yesterday_note_found": note_found,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
