"""测试章节提取器"""

from chapterbar.chapter_extractor import BASE_COLOR, extract_chapters_auto
from chapterbar.parser import SubtitleEntry


def test_extract_chapters_auto():
    """测试自动章节提取"""
    # 创建测试字幕
    entries = [
        SubtitleEntry(1, 0.0, 2.0, "开场"),
        SubtitleEntry(2, 2.0, 5.0, "介绍"),
        SubtitleEntry(3, 30.0, 35.0, "第一部分"),
        SubtitleEntry(4, 60.0, 65.0, "第二部分"),
        SubtitleEntry(5, 90.0, 95.0, "第三部分"),
    ]

    # 提取章节（每 60 秒一个）
    chapters = extract_chapters_auto(entries, interval=60, total_duration=120)

    # 验证
    assert len(chapters) == 2  # 120 秒 / 60 秒 = 2 个章节

    # 第一章
    assert chapters[0].start_time == 0
    assert chapters[0].end_time == 60
    assert "开场" in chapters[0].title or "介绍" in chapters[0].title
    assert chapters[0].color == BASE_COLOR

    # 第二章
    assert chapters[1].start_time == 60
    assert chapters[1].end_time == 120
    assert "第二部分" in chapters[1].title
    assert chapters[1].color == BASE_COLOR


def test_extract_chapters_auto_empty():
    """测试空字幕列表"""
    chapters = extract_chapters_auto([], interval=60, total_duration=120)
    assert len(chapters) == 2  # 仍然应该生成章节
    assert chapters[0].title == "章节 1"
    assert chapters[1].title == "章节 2"


def test_unified_color():
    """测试统一灰色方案"""
    entries = []
    # 创建 10 个章节
    chapters = extract_chapters_auto(entries, interval=10, total_duration=100)

    assert len(chapters) == 10
    # 验证所有章节使用相同的基础颜色
    for chapter in chapters:
        assert chapter.color == BASE_COLOR
