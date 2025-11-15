"""章节验证器"""

from dataclasses import dataclass

from chapterbar.chapter_extractor import Chapter


@dataclass
class ValidationError:
    """验证错误"""

    chapter_index: int
    error_type: str
    message: str
    is_warning: bool = False


class ChapterValidator:
    """章节验证器"""

    def __init__(self, chapters: list[Chapter], total_duration: float):
        """
        初始化验证器

        Args:
            chapters: 章节列表
            total_duration: 视频总时长（秒）
        """
        self.chapters = chapters
        self.total_duration = total_duration
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def validate(self) -> tuple[bool, list[ValidationError], list[ValidationError]]:
        """
        验证章节列表

        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # 基础检查
        self._check_empty()
        self._check_basic_fields()

        # 时间检查
        self._check_time_order()
        self._check_time_overlap()
        self._check_time_range()
        self._check_time_gaps()

        # 内容检查
        self._check_titles()
        self._check_duration()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _check_empty(self):
        """检查章节列表是否为空"""
        if not self.chapters:
            self.errors.append(ValidationError(chapter_index=-1, error_type="empty", message="章节列表为空"))

    def _check_basic_fields(self):
        """检查基本字段"""
        for i, chapter in enumerate(self.chapters):
            if not hasattr(chapter, "start_time") or chapter.start_time is None:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="missing_field",
                        message=f"章节 {i + 1} 缺少开始时间",
                    )
                )

            if not hasattr(chapter, "end_time") or chapter.end_time is None:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="missing_field",
                        message=f"章节 {i + 1} 缺少结束时间",
                    )
                )

            if not hasattr(chapter, "title") or not chapter.title:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="missing_field",
                        message=f"章节 {i + 1} 缺少标题",
                    )
                )

    def _check_time_order(self):
        """检查时间顺序"""
        for i, chapter in enumerate(self.chapters):
            if chapter.start_time >= chapter.end_time:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="time_order",
                        message=(f"章节 {i + 1} 开始时间 ({chapter.start_time}s) >= 结束时间 ({chapter.end_time}s)"),
                    )
                )

    def _check_time_overlap(self):
        """检查时间重叠"""
        for i in range(len(self.chapters) - 1):
            current = self.chapters[i]
            next_chapter = self.chapters[i + 1]

            if current.end_time > next_chapter.start_time:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="time_overlap",
                        message=(
                            f"章节 {i + 1} 和章节 {i + 2} 时间重叠：章节 {i + 1} 结束于 "
                            f"{current.end_time}s，但章节 {i + 2} 开始于 {next_chapter.start_time}s"
                        ),
                    )
                )

    def _check_time_range(self):
        """检查时间范围"""
        for i, chapter in enumerate(self.chapters):
            if chapter.start_time < 0:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="time_range",
                        message=f"章节 {i + 1} 开始时间 ({chapter.start_time}s) 不能为负数",
                    )
                )

            if chapter.end_time > self.total_duration:
                self.errors.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="time_range",
                        message=(
                            f"章节 {i + 1} 结束时间 ({chapter.end_time}s) 超出视频总时长 ({self.total_duration}s)"
                        ),
                    )
                )

    def _check_time_gaps(self):
        """检查时间间隙（警告）"""
        # 检查第一个章节是否从 0 开始
        if self.chapters and self.chapters[0].start_time > 0:
            self.warnings.append(
                ValidationError(
                    chapter_index=0,
                    error_type="time_gap",
                    message=(
                        f"第一个章节从 {self.chapters[0].start_time}s 开始，前面有 "
                        f"{self.chapters[0].start_time}s 的间隙"
                    ),
                    is_warning=True,
                )
            )

        # 检查章节之间的间隙
        for i in range(len(self.chapters) - 1):
            current = self.chapters[i]
            next_chapter = self.chapters[i + 1]

            gap = next_chapter.start_time - current.end_time
            if gap > 0:
                self.warnings.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="time_gap",
                        message=f"章节 {i + 1} 和章节 {i + 2} 之间有 {gap}s 的间隙",
                        is_warning=True,
                    )
                )

        # 检查最后一个章节是否到达视频结尾
        if self.chapters and self.chapters[-1].end_time < self.total_duration:
            gap = self.total_duration - self.chapters[-1].end_time
            self.warnings.append(
                ValidationError(
                    chapter_index=len(self.chapters) - 1,
                    error_type="time_gap",
                    message=(f"最后一个章节结束于 {self.chapters[-1].end_time}s，距离视频结尾还有 {gap}s"),
                    is_warning=True,
                )
            )

    def _check_titles(self):
        """检查标题"""
        for i, chapter in enumerate(self.chapters):
            if chapter.title and len(chapter.title.strip()) == 0:
                self.errors.append(
                    ValidationError(chapter_index=i, error_type="empty_title", message=f"章节 {i + 1} 标题为空")
                )

            if chapter.title and len(chapter.title) > 100:
                self.warnings.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="long_title",
                        message=(f"章节 {i + 1} 标题过长 ({len(chapter.title)} 字符)，建议不超过 100 字符"),
                        is_warning=True,
                    )
                )

    def _check_duration(self):
        """检查章节时长（警告）"""
        for i, chapter in enumerate(self.chapters):
            duration = chapter.end_time - chapter.start_time

            if duration < 5:
                self.warnings.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="short_duration",
                        message=f"章节 {i + 1} 时长过短 ({duration}s)，建议至少 5 秒",
                        is_warning=True,
                    )
                )

            if duration > 600:  # 10 分钟
                self.warnings.append(
                    ValidationError(
                        chapter_index=i,
                        error_type="long_duration",
                        message=f"章节 {i + 1} 时长过长 ({duration}s)，建议不超过 10 分钟",
                        is_warning=True,
                    )
                )
