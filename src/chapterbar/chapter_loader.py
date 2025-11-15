"""章节配置加载器"""

from pathlib import Path
from typing import Any

import yaml

from chapterbar.chapter_extractor import BASE_COLOR, Chapter
from chapterbar.chapter_validator import ChapterValidator


class ChapterLoader:
    """章节配置加载器"""

    @staticmethod
    def load_from_yaml(yaml_path: str) -> tuple[list[Chapter], float]:
        """
        从 YAML 文件加载章节配置

        Args:
            yaml_path: YAML 文件路径

        Returns:
            (chapters, duration)

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 配置格式错误或验证失败
        """
        # 检查文件是否存在
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {yaml_path}")

        # 读取 YAML
        try:
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}") from e

        # 验证配置结构
        if not isinstance(config, dict):
            raise ValueError("配置文件必须是一个字典")

        if "duration" not in config:
            raise ValueError("配置文件缺少 'duration' 字段")

        if "chapters" not in config:
            raise ValueError("配置文件缺少 'chapters' 字段")

        duration = float(config["duration"])
        if duration <= 0:
            raise ValueError(f"视频时长必须大于 0，当前值: {duration}")

        # 解析章节
        chapters = ChapterLoader._parse_chapters(config["chapters"])

        # 验证章节
        validator = ChapterValidator(chapters, duration)
        is_valid, errors, warnings = validator.validate()

        if not is_valid:
            error_messages = [f"  - {err.message}" for err in errors]
            raise ValueError("章节配置验证失败:\n" + "\n".join(error_messages))

        return chapters, duration, warnings

    @staticmethod
    def _parse_chapters(chapters_data: list[dict[str, Any]]) -> list[Chapter]:
        """
        解析章节数据

        Args:
            chapters_data: 章节数据列表

        Returns:
            Chapter 对象列表
        """
        if not isinstance(chapters_data, list):
            raise ValueError("'chapters' 必须是一个列表")

        chapters = []
        for i, chapter_data in enumerate(chapters_data):
            if not isinstance(chapter_data, dict):
                raise ValueError(f"章节 {i + 1} 必须是一个字典")

            # 必需字段
            if "start" not in chapter_data:
                raise ValueError(f"章节 {i + 1} 缺少 'start' 字段")
            if "end" not in chapter_data:
                raise ValueError(f"章节 {i + 1} 缺少 'end' 字段")
            if "title" not in chapter_data:
                raise ValueError(f"章节 {i + 1} 缺少 'title' 字段")

            # 解析字段
            try:
                start_time = float(chapter_data["start"])
                end_time = float(chapter_data["end"])
            except (ValueError, TypeError) as e:
                raise ValueError(f"章节 {i + 1} 时间格式错误: {e}") from e

            title = str(chapter_data["title"])

            # 可选字段：颜色
            if "color" in chapter_data:
                color_data = chapter_data["color"]
                if isinstance(color_data, list) and len(color_data) == 3:
                    color = tuple(int(c) for c in color_data)
                else:
                    raise ValueError(f"章节 {i + 1} 颜色格式错误，应为 [R, G, B]")
            else:
                color = BASE_COLOR

            chapters.append(Chapter(title=title, start_time=start_time, end_time=end_time, color=color))

        return chapters

    @staticmethod
    def save_to_yaml(chapters: list[Chapter], duration: float, yaml_path: str) -> None:
        """
        保存章节配置到 YAML 文件

        Args:
            chapters: 章节列表
            duration: 视频总时长
            yaml_path: 输出文件路径
        """
        config = {"duration": duration, "chapters": []}

        for chapter in chapters:
            chapter_data = {
                "start": chapter.start_time,
                "end": chapter.end_time,
                "title": chapter.title,
            }
            config["chapters"].append(chapter_data)

        # 写入文件
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
