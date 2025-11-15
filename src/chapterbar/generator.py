"""视频生成器 - 并行优化版本
性能优化：
1. 字体缓存 - 避免重复加载字体
2. 预计算章节布局 - 避免每帧重复计算
3. 多进程并行 - 利用多核 CPU 加速帧生成
"""

from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool, cpu_count

import numpy as np

# 使用 ImageSequenceClip 创建视频
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from PIL import Image, ImageDraw, ImageFont

from chapterbar.chapter_extractor import Chapter
from chapterbar.logger import logger

# ============================================================================
# 全局字体缓存
# ============================================================================

_font_cache: dict[int, ImageFont.FreeTypeFont | None] = {}
_font_paths = [
    "/System/Library/Fonts/STHeiti Light.ttc",  # macOS 黑体
    "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
    "/System/Library/Fonts/Hiragino Sans GB.ttc",  # macOS
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
    "C:\\Windows\\Fonts\\msyh.ttc",  # Windows 微软雅黑
    "C:\\Windows\\Fonts\\simhei.ttf",  # Windows 黑体
]


def get_cached_font(size: int) -> ImageFont.FreeTypeFont | None:
    """获取缓存的字体

    Args:
        size: 字体大小

    Returns:
        字体对象，如果加载失败则返回 None
    """
    if size not in _font_cache:
        font = None
        for font_path in _font_paths:
            try:
                font = ImageFont.truetype(font_path, size)
                break
            except Exception:
                continue

        # 如果所有字体都失败，尝试 Arial
        if font is None:
            try:
                font = ImageFont.truetype("Arial.ttf", size)
            except Exception:
                font = ImageFont.load_default()

        _font_cache[size] = font

    return _font_cache[size]


# ============================================================================
# 预计算章节布局
# ============================================================================


@dataclass
class ChapterLayout:
    """预计算的章节布局信息"""

    x_offset: int
    width: int
    title: str
    original_title: str  # 原始标题（未截断）
    font_size: int
    text_x: int
    text_y: int
    text_width: int
    text_height: int
    should_draw_text: bool  # 是否应该绘制文字


def precompute_chapter_layouts(
    chapters: list[Chapter], width: int, height: int, duration: float
) -> list[ChapterLayout]:
    """预计算所有章节的布局信息

    Args:
        chapters: 章节列表
        width: 视频宽度
        height: 进度条高度
        duration: 视频总时长

    Returns:
        章节布局列表
    """
    layouts = []
    x_offset = 0

    for chapter in chapters:
        # 计算章节宽度
        chapter_duration = chapter.end_time - chapter.start_time
        chapter_width = int((chapter_duration / duration) * width)

        # 如果章节太窄，跳过文字
        if chapter_width < 50:
            layouts.append(
                ChapterLayout(
                    x_offset=x_offset,
                    width=chapter_width,
                    title="",
                    original_title=chapter.title,
                    font_size=0,
                    text_x=0,
                    text_y=0,
                    text_width=0,
                    text_height=0,
                    should_draw_text=False,
                )
            )
            x_offset += chapter_width
            continue

        # 计算文字布局
        text = chapter.title
        font_size = 20
        font = get_cached_font(font_size)

        # 创建临时 draw 对象用于测量
        temp_img = Image.new("RGBA", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)

        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 如果文字太长，逐步缩小字号
        while text_width > chapter_width - 20 and font_size > 12:
            font_size -= 2
            font = get_cached_font(font_size)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

        # 如果还是太长，截断文字
        if text_width > chapter_width - 20:
            while text and text_width > chapter_width - 20:
                text = text[:-1]
                bbox = temp_draw.textbbox((0, 0), text + "...", font=font)
                text_width = bbox[2] - bbox[0]
            if text:
                text = text + "..."

        # 计算文字位置（居中）
        text_x = x_offset + (chapter_width - text_width) // 2
        text_y = (height - text_height) // 2

        layouts.append(
            ChapterLayout(
                x_offset=x_offset,
                width=chapter_width,
                title=text,
                original_title=chapter.title,
                font_size=font_size,
                text_x=text_x,
                text_y=text_y,
                text_width=text_width,
                text_height=text_height,
                should_draw_text=bool(text),
            )
        )

        x_offset += chapter_width

    return layouts


# ============================================================================
# 优化的帧生成函数
# ============================================================================


def create_chapter_bar_frame_optimized(
    t: float,
    chapters: list[Chapter],
    layouts: list[ChapterLayout],
    width: int,
    height: int,
    duration: float,
) -> np.ndarray:
    """创建章节条的单帧图像（优化版本）

    Args:
        t: 当前时间（秒）
        chapters: 章节列表
        layouts: 预计算的章节布局
        width: 视频宽度
        height: 进度条高度
        duration: 视频总时长

    Returns:
        np.ndarray: RGBA 图像数组
    """
    # 定义颜色方案
    COLOR_UNWATCHED = (220, 220, 220)  # 未播放：浅灰色
    COLOR_WATCHED = (140, 140, 140)  # 已播放：深灰色
    COLOR_SEPARATOR = (100, 100, 100)  # 分隔线：更深灰色

    # 创建透明背景
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 绘制章节条
    for i, (chapter, layout) in enumerate(zip(chapters, layouts, strict=True)):
        # 判断章节状态并绘制
        if chapter.end_time <= t:
            # 完全播放完 → 深灰色
            draw.rectangle(
                [layout.x_offset, 0, layout.x_offset + layout.width, height],
                fill=COLOR_WATCHED + (255,),
            )
        elif chapter.start_time <= t < chapter.end_time:
            # 当前章节 → 分段绘制
            chapter_duration = chapter.end_time - chapter.start_time
            played_duration = t - chapter.start_time
            played_width = int((played_duration / chapter_duration) * layout.width)

            # 已播放部分：深灰色
            if played_width > 0:
                draw.rectangle(
                    [layout.x_offset, 0, layout.x_offset + played_width, height],
                    fill=COLOR_WATCHED + (255,),
                )

            # 未播放部分：浅灰色
            if played_width < layout.width:
                draw.rectangle(
                    [layout.x_offset + played_width, 0, layout.x_offset + layout.width, height],
                    fill=COLOR_UNWATCHED + (255,),
                )
        else:
            # 未播放 → 浅灰色
            draw.rectangle(
                [layout.x_offset, 0, layout.x_offset + layout.width, height],
                fill=COLOR_UNWATCHED + (255,),
            )

        # 绘制章节分隔线（除了第一个章节）
        if i > 0:
            draw.line(
                [(layout.x_offset, 0), (layout.x_offset, height)],
                fill=COLOR_SEPARATOR + (255,),
                width=2,
            )

        # 绘制章节标题（使用预计算的布局）
        if layout.should_draw_text:
            font = get_cached_font(layout.font_size)

            # 根据章节状态选择文字颜色
            if chapter.end_time <= t:
                # 已播放章节：深灰色背景 → 白色文字
                text_color = (255, 255, 255, 255)
                shadow_color = (0, 0, 0, 120)
            elif chapter.start_time <= t < chapter.end_time:
                # 当前章节：混合背景 → 白色文字
                text_color = (255, 255, 255, 255)
                shadow_color = (0, 0, 0, 120)
            else:
                # 未播放章节：浅灰色背景 → 深灰色文字
                text_color = (80, 80, 80, 255)
                shadow_color = (255, 255, 255, 120)

            # 绘制文字阴影
            draw.text((layout.text_x + 1, layout.text_y + 1), layout.title, fill=shadow_color, font=font)
            # 绘制文字
            draw.text((layout.text_x, layout.text_y), layout.title, fill=text_color, font=font)

    # 绘制进度指针（白色竖线，4px 宽）
    pointer_x = int((t / duration) * width)
    # 绘制指针阴影
    draw.rectangle([pointer_x - 3, 0, pointer_x + 3, height], fill=(0, 0, 0, 100))
    # 绘制指针主体
    draw.rectangle([pointer_x - 2, 0, pointer_x + 2, height], fill=(255, 255, 255, 255))

    # 转换为 numpy 数组
    return np.array(img)


# ============================================================================
# 并行帧生成
# ============================================================================


def generate_frame_batch(
    frame_indices: list[int],
    chapters: list[Chapter],
    layouts: list[ChapterLayout],
    width: int,
    height: int,
    duration: float,
    fps: int,
) -> list[tuple[int, np.ndarray]]:
    """生成一批帧（用于并行处理）

    Args:
        frame_indices: 要生成的帧索引列表
        chapters: 章节列表
        layouts: 预计算的章节布局
        width: 视频宽度
        height: 进度条高度
        duration: 视频总时长
        fps: 帧率

    Returns:
        (帧索引, 帧数据) 的列表
    """
    frames = []
    for frame_num in frame_indices:
        t = frame_num / fps
        frame = create_chapter_bar_frame_optimized(t, chapters, layouts, width, height, duration)
        frames.append((frame_num, frame))
    return frames


# ============================================================================
# 优化的视频生成函数（支持并行）
# ============================================================================


def generate_video(
    chapters: list[Chapter],
    output_path: str,
    width: int = 1920,
    height: int = 60,
    duration: float = None,
    fps: int = 30,
    use_parallel: bool = True,
    num_workers: int | None = None,
) -> None:
    """生成章节进度条视频（支持并行优化）

    Args:
        chapters: 章节列表
        output_path: 输出文件路径
        width: 视频宽度
        height: 进度条高度
        duration: 视频总时长（秒）
        fps: 帧率
        use_parallel: 是否使用并行处理（默认 True）
        num_workers: 并行工作进程数（默认为 CPU 核心数）
    """
    if duration is None:
        duration = chapters[-1].end_time if chapters else 10

    # 预计算章节布局（只计算一次）
    logger.info("正在预计算章节布局...")
    layouts = precompute_chapter_layouts(chapters, width, height, duration)
    logger.info(f"布局计算完成，共 {len(layouts)} 个章节")

    total_frames = int(duration * fps)

    # 根据帧数决定是否使用并行
    # 帧数太少时，并行开销可能大于收益
    if total_frames < 300:
        use_parallel = False
        logger.info(f"帧数较少 ({total_frames} 帧)，使用串行生成")

    if use_parallel:
        # 并行生成帧
        if num_workers is None:
            num_workers = cpu_count()

        logger.info(f"正在并行生成 {total_frames} 帧（使用 {num_workers} 个进程）...")

        # 分批：将帧索引分配给各个进程
        batch_size = (total_frames + num_workers - 1) // num_workers
        frame_batches = []
        for i in range(num_workers):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, total_frames)
            if start_idx < total_frames:
                frame_batches.append(list(range(start_idx, end_idx)))

        # 创建部分函数（固定参数）
        batch_func = partial(
            generate_frame_batch,
            chapters=chapters,
            layouts=layouts,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
        )

        # 并行生成
        with Pool(num_workers) as pool:
            results = pool.map(batch_func, frame_batches)

        # 合并结果并按帧索引排序
        all_frames = []
        for batch_result in results:
            all_frames.extend(batch_result)

        # 按帧索引排序
        all_frames.sort(key=lambda x: x[0])
        frames = [frame for _, frame in all_frames]

        logger.info("并行帧生成完成")
    else:
        # 串行生成帧（原有逻辑）
        logger.info(f"正在生成 {total_frames} 帧...")
        frames = []

        last_progress = -1
        for frame_num in range(total_frames):
            t = frame_num / fps
            frame = create_chapter_bar_frame_optimized(t, chapters, layouts, width, height, duration)
            frames.append(frame)

            # 显示进度（每 5% 显示一次）
            progress = int((frame_num + 1) / total_frames * 100)
            if progress % 5 == 0 and progress != last_progress:
                logger.info(f"进度: {frame_num + 1}/{total_frames} ({progress}%)")
                last_progress = progress

        logger.info("帧生成完成")

    clip = ImageSequenceClip(frames, fps=fps)

    # 输出视频
    logger.info("正在编码视频...")
    try:
        clip.write_videofile(
            output_path,
            fps=fps,
            codec="qtrle",  # QuickTime Animation codec with alpha
            audio=False,
            logger=None,
            ffmpeg_params=["-pix_fmt", "argb"],
            preset="ultrafast",  # 加快编码速度
        )
    except Exception as e:
        # 如果 qtrle 失败，尝试使用 png
        logger.warning(f"qtrle 编码失败，使用 png 编码: {e}")
        clip.write_videofile(output_path, fps=fps, codec="png", audio=False, logger=None)

    logger.info("视频生成完成")


# ============================================================================
# 向后兼容：保留原函数名
# ============================================================================


def create_chapter_bar_frame(t: float, chapters: list[Chapter], width: int, height: int, duration: float) -> np.ndarray:
    """创建章节条的单帧图像（向后兼容的包装函数）

    注意：此函数为向后兼容保留，性能较差。
    建议使用 create_chapter_bar_frame_optimized 配合预计算布局。
    """
    # 每次调用都重新计算布局（性能较差）
    layouts = precompute_chapter_layouts(chapters, width, height, duration)
    return create_chapter_bar_frame_optimized(t, chapters, layouts, width, height, duration)
