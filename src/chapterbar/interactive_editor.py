"""交互式章节编辑器"""

from rich.console import Console
from rich.table import Table

from chapterbar.chapter_extractor import BASE_COLOR, Chapter
from chapterbar.chapter_validator import ChapterValidator

console = Console()


def format_time(seconds: float) -> str:
    """格式化时间为 mm:ss"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def parse_time_input(time_str: str) -> float | None:
    """解析时间输入（支持 mm:ss 或秒数）"""
    time_str = time_str.strip()
    if not time_str:
        return None

    try:
        # 尝试解析为秒数
        return float(time_str)
    except ValueError:
        pass

    # 尝试解析为 mm:ss 格式
    if ":" in time_str:
        try:
            parts = time_str.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
        except ValueError:
            pass

    return None


def display_chapters_table(chapters: list[Chapter], title: str = "章节列表"):
    """显示章节列表"""
    table = Table(title=title)
    table.add_column("序号", style="cyan")
    table.add_column("开始时间", style="magenta")
    table.add_column("结束时间", style="magenta")
    table.add_column("标题", style="green")

    for i, chapter in enumerate(chapters, 1):
        table.add_row(str(i), format_time(chapter.start_time), format_time(chapter.end_time), chapter.title)

    console.print(table)


def edit_chapter(chapters: list[Chapter], index: int, duration: float) -> bool:
    """编辑单个章节"""
    if index < 0 or index >= len(chapters):
        console.print("[red]✗ 无效的章节序号[/red]")
        return False

    chapter = chapters[index]
    console.print(f"\n[cyan]编辑章节 {index + 1}:[/cyan]")
    console.print(f"当前: {format_time(chapter.start_time)} - {format_time(chapter.end_time)} | {chapter.title}")
    console.print()

    # 编辑开始时间
    start_input = input(f"开始时间 (mm:ss 或秒数，留空保持 {format_time(chapter.start_time)}): ").strip()
    if start_input:
        new_start = parse_time_input(start_input)
        if new_start is None:
            console.print("[red]✗ 无效的时间格式[/red]")
            return False
        chapter.start_time = new_start

    # 编辑结束时间
    end_input = input(f"结束时间 (mm:ss 或秒数，留空保持 {format_time(chapter.end_time)}): ").strip()
    if end_input:
        new_end = parse_time_input(end_input)
        if new_end is None:
            console.print("[red]✗ 无效的时间格式[/red]")
            return False
        chapter.end_time = new_end

    # 编辑标题
    title_input = input(f"标题 (留空保持 '{chapter.title}'): ").strip()
    if title_input:
        chapter.title = title_input

    console.print(f"[green]✓ 章节 {index + 1} 已更新[/green]\n")
    return True


def add_chapter(chapters: list[Chapter], duration: float) -> bool:
    """添加新章节"""
    console.print("\n[cyan]添加新章节:[/cyan]")

    # 输入开始时间
    start_input = input("开始时间 (mm:ss 或秒数): ").strip()
    start_time = parse_time_input(start_input)
    if start_time is None:
        console.print("[red]✗ 无效的时间格式[/red]")
        return False

    # 输入结束时间
    end_input = input("结束时间 (mm:ss 或秒数): ").strip()
    end_time = parse_time_input(end_input)
    if end_time is None:
        console.print("[red]✗ 无效的时间格式[/red]")
        return False

    # 输入标题
    title = input("标题: ").strip()
    if not title:
        console.print("[red]✗ 标题不能为空[/red]")
        return False

    # 创建新章节
    new_chapter = Chapter(title=title, start_time=start_time, end_time=end_time, color=BASE_COLOR)

    # 插入到合适的位置（按开始时间排序）
    insert_pos = len(chapters)
    for i, ch in enumerate(chapters):
        if new_chapter.start_time < ch.start_time:
            insert_pos = i
            break

    chapters.insert(insert_pos, new_chapter)
    console.print(f"[green]✓ 章节已添加到位置 {insert_pos + 1}[/green]\n")
    return True


def delete_chapter(chapters: list[Chapter], index: int) -> bool:
    """删除章节"""
    if index < 0 or index >= len(chapters):
        console.print("[red]✗ 无效的章节序号[/red]")
        return False

    removed = chapters.pop(index)
    console.print(f"[green]✓ 已删除章节 {index + 1}: {removed.title}[/green]\n")
    return True


def interactive_edit_chapters(chapters: list[Chapter], duration: float) -> list[Chapter] | None:
    """交互式编辑章节

    返回:
        编辑后的章节列表，如果用户取消则返回 None
    """
    # 创建副本，避免修改原始数据
    chapters = [Chapter(ch.title, ch.start_time, ch.end_time, ch.color) for ch in chapters]

    console.print("\n[bold cyan]📝 编辑模式[/bold cyan]")
    console.print("\n可用命令:")
    console.print("  [数字]     - 编辑章节 (如: 1)")
    console.print("  [d数字]    - 删除章节 (如: d2)")
    console.print("  [a]        - 添加章节")
    console.print("  [l]        - 显示章节列表")
    console.print("  [done]     - 完成编辑并继续")
    console.print("  [cancel]   - 取消编辑\n")

    while True:
        cmd = input("> ").strip().lower()

        if cmd == "done":
            # 验证章节
            console.print("\n[cyan]正在验证章节...[/cyan]")
            errors = ChapterValidator.validate_chapters(chapters, duration)

            if errors:
                console.print("[red]✗ 验证失败:[/red]")
                for error in errors:
                    console.print(f"[red]  - {error.message}[/red]")
                console.print("\n[yellow]请修正错误后再试，或输入 'cancel' 取消编辑[/yellow]\n")
                continue

            console.print("[green]✓ 验证通过[/green]\n")
            return chapters

        elif cmd == "cancel":
            console.print("[yellow]已取消编辑[/yellow]\n")
            return None

        elif cmd == "l":
            display_chapters_table(chapters)
            console.print()

        elif cmd == "a":
            if add_chapter(chapters, duration):
                display_chapters_table(chapters)
                console.print()

        elif cmd.startswith("d") and len(cmd) > 1:
            try:
                index = int(cmd[1:]) - 1
                if delete_chapter(chapters, index):
                    display_chapters_table(chapters)
                    console.print()
            except ValueError:
                console.print("[red]✗ 无效的命令格式，使用 'd数字' 删除章节 (如: d2)[/red]\n")

        elif cmd.isdigit():
            index = int(cmd) - 1
            if edit_chapter(chapters, index, duration):
                display_chapters_table(chapters)
                console.print()

        elif cmd:
            console.print("[red]✗ 无效的命令，输入 'l' 查看帮助[/red]\n")


def confirm_chapters(chapters: list[Chapter], skip_confirm: bool = False) -> list[Chapter] | None:
    """确认章节配置

    参数:
        chapters: 章节列表
        skip_confirm: 是否跳过确认（--yes 参数）

    返回:
        确认或编辑后的章节列表，如果用户退出则返回 None
    """
    if skip_confirm:
        return chapters

    console.print("\n[bold]请选择操作:[/bold]")
    console.print("  [y] 确认并生成视频")
    console.print("  [e] 编辑章节")
    console.print("  [q] 退出\n")

    while True:
        choice = input("> ").strip().lower()

        if choice == "y":
            console.print("[green]✓ 已确认，开始生成视频...[/green]\n")
            return chapters

        elif choice == "e":
            # 获取视频时长（从最后一个章节）
            duration = chapters[-1].end_time if chapters else 0
            edited_chapters = interactive_edit_chapters(chapters, duration)

            if edited_chapters is None:
                # 用户取消编辑，回到确认界面
                console.print("\n[bold]请选择操作:[/bold]")
                console.print("  [y] 确认并生成视频")
                console.print("  [e] 编辑章节")
                console.print("  [q] 退出\n")
                continue

            return edited_chapters

        elif choice == "q":
            console.print("[yellow]已退出[/yellow]")
            return None

        else:
            console.print("[red]✗ 无效的选择，请输入 y/e/q[/red]\n")
