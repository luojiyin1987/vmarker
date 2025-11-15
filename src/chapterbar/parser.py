"""SRT 字幕文件解析器"""

import re
from dataclasses import dataclass


@dataclass
class SubtitleEntry:
    """字幕条目"""

    index: int
    start_time: float  # 秒
    end_time: float  # 秒
    text: str


def parse_timestamp(timestamp: str) -> float:
    """将 HH:MM:SS,mmm 格式转换为秒数

    Args:
        timestamp: 时间戳字符串，如 "00:01:23,456"

    Returns:
        float: 秒数
    """
    # 匹配格式：HH:MM:SS,mmm
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", timestamp)
    if not match:
        raise ValueError(f"无效的时间戳格式: {timestamp}")

    hours, minutes, seconds, milliseconds = map(int, match.groups())
    total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
    return total_seconds


def parse_srt(file_path: str) -> list[SubtitleEntry]:
    """解析 SRT 字幕文件

    Args:
        file_path: SRT 文件路径

    Returns:
        List[SubtitleEntry]: 字幕条目列表
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    entries = []
    # 按空行分割字幕块
    blocks = content.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        # 第一行是序号
        try:
            index = int(lines[0])
        except ValueError:
            continue

        # 第二行是时间戳
        timestamp_line = lines[1]
        match = re.match(r"(.+?)\s*-->\s*(.+)", timestamp_line)
        if not match:
            continue

        start_str, end_str = match.groups()
        start_time = parse_timestamp(start_str.strip())
        end_time = parse_timestamp(end_str.strip())

        # 剩余行是文本内容
        text = " ".join(lines[2:])

        entries.append(SubtitleEntry(index=index, start_time=start_time, end_time=end_time, text=text))

    return entries
