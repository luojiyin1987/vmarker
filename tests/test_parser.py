"""测试 SRT 解析器"""

import pytest

from chapterbar.parser import parse_srt, parse_timestamp


def test_parse_timestamp():
    """测试时间戳解析"""
    assert parse_timestamp("00:00:00,000") == 0.0
    assert parse_timestamp("00:00:01,000") == 1.0
    assert parse_timestamp("00:01:00,000") == 60.0
    assert parse_timestamp("01:00:00,000") == 3600.0
    assert parse_timestamp("00:00:00,500") == 0.5
    assert parse_timestamp("00:01:23,456") == 83.456


def test_parse_timestamp_invalid():
    """测试无效时间戳"""
    with pytest.raises(ValueError):
        parse_timestamp("invalid")
    with pytest.raises(ValueError):
        parse_timestamp("00:00:00")  # 缺少毫秒


def test_parse_srt(tmp_path):
    """测试 SRT 文件解析"""
    # 创建测试 SRT 文件
    srt_content = """1
00:00:00,000 --> 00:00:02,000
第一行字幕

2
00:00:02,000 --> 00:00:05,000
第二行字幕
多行文本

3
00:00:05,000 --> 00:00:08,000
第三行字幕
"""

    srt_file = tmp_path / "test.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    # 解析
    entries = parse_srt(str(srt_file))

    # 验证
    assert len(entries) == 3

    assert entries[0].index == 1
    assert entries[0].start_time == 0.0
    assert entries[0].end_time == 2.0
    assert entries[0].text == "第一行字幕"

    assert entries[1].index == 2
    assert entries[1].start_time == 2.0
    assert entries[1].end_time == 5.0
    assert entries[1].text == "第二行字幕 多行文本"

    assert entries[2].index == 3
    assert entries[2].start_time == 5.0
    assert entries[2].end_time == 8.0
    assert entries[2].text == "第三行字幕"
