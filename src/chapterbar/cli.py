"""命令行界面"""

from pathlib import Path

import typer
from rich.console import Console

from chapterbar.chapter_extractor import extract_chapters_ai, extract_chapters_auto
from chapterbar.chapter_loader import ChapterLoader
from chapterbar.generator import generate_video
from chapterbar.interactive_editor import display_chapters_table
from chapterbar.parser import parse_srt

app = typer.Typer(help="Auto-Chapter-Bar - 视频章节进度条生成器")
console = Console()


@app.command()
def main(
    srt_file: Path | None = typer.Argument(None, help="SRT 字幕文件路径（可选，使用 --chapters 时不需要）"),
    duration: float | None = typer.Argument(None, help="视频总时长（秒），不提供则从 SRT 文件自动获取"),
    output: Path = typer.Option("chapter_bar.mov", "--output", "-o", help="输出文件路径"),
    width: int = typer.Option(1920, "--width", "-w", help="视频宽度"),
    height: int = typer.Option(60, "--height", "-h", help="进度条高度"),
    mode: str = typer.Option(
        "ai",
        "--mode",
        "-m",
        help="章节提取模式：auto（固定间隔）、ai（智能分段，默认）或 manual（手动配置）",
    ),
    interval: int = typer.Option(60, "--interval", "-i", help="自动分段间隔（秒），仅在 auto 模式下使用"),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Moonshot API Key（AI 模式需要，也可通过环境变量 MOONSHOT_API_KEY 设置）",
    ),
    model: str = typer.Option("moonshot-v1-8k", "--model", help="AI 模型名称（默认 moonshot-v1-8k）"),
    auto_confirm: bool = typer.Option(False, "--yes", "-y", help="自动确认所有提示（跳过时长确认和章节编辑）"),
    chapters_file: Path | None = typer.Option(None, "--chapters", help="手动章节配置文件（YAML 格式）"),
    save_chapters: Path | None = typer.Option(None, "--save-chapters", help="保存生成的章节配置到 YAML 文件"),
):
    """生成视频章节进度条"""

    try:
        # 1. 检查是否使用手动配置文件
        if chapters_file:
            console.print(f"[cyan]📄 正在加载章节配置文件: {chapters_file}[/cyan]")
            try:
                chapters, duration, warnings = ChapterLoader.load_from_yaml(str(chapters_file))
                console.print(f"[green]✓ 配置加载成功，共 {len(chapters)} 个章节[/green]")
                console.print(f"[cyan]📏 视频时长: {duration:.2f} 秒 ({duration / 60:.2f} 分钟)[/cyan]")

                # 显示警告
                if warnings:
                    console.print(f"\n[yellow]⚠️  发现 {len(warnings)} 个警告：[/yellow]")
                    for warning in warnings:
                        console.print(f"[yellow]  - {warning.message}[/yellow]")
                    console.print()

                # 跳过 SRT 解析，直接到章节显示
                entries = None

            except (FileNotFoundError, ValueError) as e:
                console.print(f"[red]✗ 错误: {e}[/red]")
                raise typer.Exit(1) from e

        # 2. 解析 SRT 文件（如果没有使用配置文件）
        elif srt_file:
            console.print(f"[cyan]正在解析 SRT 文件: {srt_file}[/cyan]")
            entries = parse_srt(str(srt_file))
            console.print(f"[green]✓ 解析完成，共 {len(entries)} 条字幕[/green]")

            if not entries:
                console.print("[red]✗ 错误: SRT 文件为空[/red]")
                raise typer.Exit(1)
        else:
            console.print("[red]✗ 错误: 必须提供 SRT 文件或章节配置文件（--chapters）[/red]")
            raise typer.Exit(1)

        # 3. 处理视频时长（如果没有使用配置文件）
        if not chapters_file:
            srt_duration = entries[-1].end_time

            if duration is None:
                # 用户未提供时长，自动从 SRT 获取
                duration = srt_duration
                console.print(
                    f"[cyan]📏 从 SRT 文件自动获取视频时长: {duration:.2f} 秒 ({duration / 60:.2f} 分钟)[/cyan]"
                )
            else:
                # 用户提供了时长，检查是否与 SRT 一致
                console.print(f"[cyan]📏 用户指定视频时长: {duration:.2f} 秒 ({duration / 60:.2f} 分钟)[/cyan]")
                console.print(f"[cyan]📏 SRT 文件实际时长: {srt_duration:.2f} 秒 ({srt_duration / 60:.2f} 分钟)[/cyan]")

                # 如果差异超过 5 秒，显示警告
                if abs(duration - srt_duration) > 5:
                    console.print("\n[yellow]⚠️  警告: 指定时长与 SRT 实际时长不一致！[/yellow]")
                    console.print(f"[yellow]   差异: {abs(duration - srt_duration):.2f} 秒[/yellow]\n")

                    if not auto_confirm:
                        # 询问用户选择
                        console.print("请选择使用哪个时长：")
                        console.print(f"  [1] 使用 SRT 时长: {srt_duration:.2f} 秒 (推荐)")
                        console.print(f"  [2] 使用指定时长: {duration:.2f} 秒")
                        console.print("  [3] 取消操作")

                        choice = typer.prompt("\n请输入选择 (1/2/3)", default="1")

                        if choice == "1":
                            duration = srt_duration
                            console.print(f"[green]✓ 使用 SRT 时长: {duration:.2f} 秒[/green]\n")
                        elif choice == "2":
                            console.print(f"[green]✓ 使用指定时长: {duration:.2f} 秒[/green]\n")
                        else:
                            console.print("[yellow]已取消操作[/yellow]")
                            raise typer.Exit(0)
                    else:
                        # 自动确认模式，使用 SRT 时长
                        duration = srt_duration
                        console.print(f"[green]✓ 自动使用 SRT 时长: {duration:.2f} 秒[/green]\n")

        # 4. 提取章节（如果没有使用配置文件）
        if chapters_file:
            # 已经从配置文件加载了章节，跳过
            pass
        elif mode == "ai":
            console.print(f"[cyan]🤖 正在使用 AI 智能分段（模型: {model}）...[/cyan]")
            console.print("[yellow]这可能需要几秒钟，请稍候...[/yellow]")
            chapters = extract_chapters_ai(entries, duration, api_key, model)
            console.print(f"[green]✓ AI 分段完成，共 {len(chapters)} 个章节[/green]\n")
        else:
            console.print(f"[cyan]正在提取章节（间隔: {interval}秒）...[/cyan]")
            chapters = extract_chapters_auto(entries, interval, duration)
            console.print(f"[green]✓ 提取完成，共 {len(chapters)} 个章节[/green]\n")

        # 5. 保存章节配置（如果指定了 --save-chapters）
        if save_chapters:
            console.print(f"\n[cyan]💾 正在保存章节配置到: {save_chapters}[/cyan]")
            try:
                ChapterLoader.save_to_yaml(chapters, duration, str(save_chapters))
                console.print("[green]✓ 章节配置已保存[/green]")
                console.print(f"[cyan]💡 提示: 可以编辑 {save_chapters} 后使用 --chapters 参数重新生成[/cyan]\n")
            except Exception as e:
                console.print(f"[yellow]⚠️  保存配置失败: {e}[/yellow]\n")

        # 6. 显示章节列表
        display_chapters_table(chapters)
        console.print()

        # 7. 交互式确认（仅在 AI 或 Auto 模式下，且未使用配置文件时）
        # if not chapters_file and mode in ["ai", "auto"]:
        #     chapters = confirm_chapters(chapters, skip_confirm=auto_confirm)
        #     if chapters is None:
        #         # 用户选择退出
        #         raise typer.Exit(0)

        # 8. 生成视频
        console.print(f"[cyan]正在生成视频: {output}[/cyan]")
        console.print("[yellow]这可能需要几分钟时间，请耐心等待...[/yellow]")

        generate_video(
            chapters=chapters,
            output_path=str(output),
            width=width,
            height=height,
            duration=duration,
        )

        console.print(f"[green]✓ 视频生成完成: {output}[/green]")
        console.print("\n[bold]使用说明：[/bold]")
        console.print("1. 在剪辑软件（PR/剪映/达芬奇）中打开原视频")
        console.print("2. 将生成的章节条视频拖入最上层轨道")
        console.print("3. 调整位置和大小，导出最终视频")

    except Exception as e:
        console.print(f"[red]✗ 错误: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
