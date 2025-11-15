"""章节提取器"""

import json
import os
import re
from dataclasses import dataclass

import openai

from chapterbar.logger import logger
from chapterbar.parser import SubtitleEntry


@dataclass
class Chapter:
    """章节信息"""

    title: str
    start_time: float  # 秒
    end_time: float  # 秒
    color: tuple[int, int, int]  # RGB


# 统一灰色方案（实际颜色在渲染时根据播放状态决定）
# 未播放：浅灰色 (220, 220, 220)
# 已播放：深灰色 (140, 140, 140)
BASE_COLOR = (200, 200, 200)  # 默认灰色


def extract_chapters_auto(entries: list[SubtitleEntry], interval: int, total_duration: float) -> list[Chapter]:
    """自动分段模式：按时间间隔分段

    Args:
        entries: 字幕条目列表
        interval: 分段间隔（秒）
        total_duration: 视频总时长（秒）

    Returns:
        List[Chapter]: 章节列表
    """
    chapters = []
    current_time = 0
    chapter_index = 0

    while current_time < total_duration:
        # 计算章节结束时间
        end_time = min(current_time + interval, total_duration)

        # 找到这个时间段内的字幕文本作为标题
        title_parts = []
        if entries:  # 只有当有字幕时才尝试提取
            for entry in entries:
                if current_time <= entry.start_time < end_time:
                    title_parts.append(entry.text)
                    if len(title_parts) >= 3:  # 最多取3条字幕
                        break

        # 生成标题
        title = " ".join(title_parts)[:30] if title_parts else f"章节 {chapter_index + 1}"

        # 使用统一的基础颜色
        color = BASE_COLOR

        chapters.append(Chapter(title=title, start_time=current_time, end_time=end_time, color=color))

        current_time = end_time
        chapter_index += 1

    return chapters


def format_time(seconds: float) -> str:
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def extract_chapters_ai(
    entries: list[SubtitleEntry],
    total_duration: float,
    api_key: str | None = None,
    model: str = "moonshot-v1-8k",
) -> list[Chapter]:
    """AI 智能分段模式：使用 Moonshot AI 分析字幕内容

    Args:
        entries: 字幕条目列表
        total_duration: 视频总时长（秒）
        api_key: Moonshot API Key（可选，默认从环境变量读取）
        model: 使用的模型（默认 moonshot-v1-8k）

    Returns:
        List[Chapter]: 章节列表
    """
    if not entries:
        # 如果没有字幕，回退到自动分段
        return extract_chapters_auto(entries, interval=60, total_duration=total_duration)

    # 获取 API Key
    if api_key is None:
        api_key = os.getenv("MOONSHOT_API_KEY")

    if not api_key:
        raise ValueError("未提供 Moonshot API Key，请设置环境变量 MOONSHOT_API_KEY 或通过参数传入")

    # 初始化客户端
    client = openai.Client(base_url="https://api.moonshot.cn/v1", api_key=api_key)

    # 构建字幕文本（带时间戳）
    subtitle_lines = []
    for entry in entries:
        time_str = format_time(entry.start_time)
        subtitle_lines.append(f"[{time_str}] {entry.text}")

    subtitle_text = "\n".join(subtitle_lines)

    # 构建 prompt
    prompt = f"""请分析以下视频字幕内容，识别内容的主题转换点，并生成合理的章节划分。

要求：
1. 识别 5-10 个主要章节（根据内容长度和复杂度调整）
2. 每个章节给出开始时间（格式：HH:MM:SS）和简短标题（5-15 字）
3. 章节标题要准确概括该段内容的核心主题
4. 返回 JSON 格式数组，每个元素包含 time 和 title 字段
5. 视频总时长为 {format_time(total_duration)}

示例输出格式：
[
  {{"time": "00:00:00", "title": "开场与自我介绍"}},
  {{"time": "00:01:23", "title": "问题背景分析"}},
  {{"time": "00:03:45", "title": "解决方案详解"}}
]

字幕内容：
{subtitle_text}

请直接返回 JSON 数组，不要包含其他说明文字。"""

    # 调用 API
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的视频内容分析助手，擅长识别内容结构和主题转换点。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # 较低的温度以获得更稳定的输出
            max_tokens=2048,
        )

        # 解析响应
        content = response.choices[0].message.content.strip()

        # 提取 JSON（可能被包裹在代码块中）
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content

        # 解析 JSON
        chapter_data = json.loads(json_str)

        # 转换为 Chapter 对象
        chapters = []
        for i, item in enumerate(chapter_data):
            # 解析时间
            time_str = item["time"]
            time_parts = time_str.split(":")
            start_time = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])

            # 计算结束时间
            if i < len(chapter_data) - 1:
                next_time_str = chapter_data[i + 1]["time"]
                next_time_parts = next_time_str.split(":")
                end_time = int(next_time_parts[0]) * 3600 + int(next_time_parts[1]) * 60 + int(next_time_parts[2])
            else:
                end_time = total_duration

            # 使用统一的基础颜色
            color = BASE_COLOR

            chapters.append(Chapter(title=item["title"], start_time=start_time, end_time=end_time, color=color))

        return chapters

    except json.JSONDecodeError as e:
        logger.warning(f"AI 返回的内容无法解析为 JSON: {e}")
        logger.debug(f"原始内容: {content}")
        # 回退到自动分段
        return extract_chapters_auto(entries, interval=60, total_duration=total_duration)

    except Exception as e:
        logger.warning(f"AI 分段失败: {e}")
        # 回退到自动分段
        return extract_chapters_auto(entries, interval=60, total_duration=total_duration)
