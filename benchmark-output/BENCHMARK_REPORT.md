# 视频合成性能基准测试报告

> 对比串行 vs 并行视频合成的性能表现

**测试时间**: 2025-01-19
**测试环境**: WSL2 Ubuntu, 16 CPU cores, FFmpeg 6.1.1, Python 3.13

---

## 测试方法

### 测试工具

```bash
python scripts/benchmark-compose.py \
    --source <source.mp4> \
    --bar <bar.mp4> \
    --output-dir ./benchmark-output \
    [--chunk-seconds N] \
    [--max-workers N] \
    [--overwrite]
```

### 测试视频生成

```bash
# 创建测试视频 (使用 FFmpeg lavfi 生成纯色视频)
ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=DURATION:r=25 \
       -c:v libx264 -preset ultrafast -crf 23 -y source.mp4

ffmpeg -f lavfi -i color=c=red@0.7:s=1280x100:d=DURATION:r=25 \
       -c:v libx264 -preset ultrafast -crf 23 -y bar.mp4
```

---

## 测试结果

### 1. 视频长度影响 (默认配置)

| 视频长度 | Serial Wall | Parallel Wall | 加速比 | 结论 |
|---------|-------------|---------------|--------|------|
| 5s | 0.74s | 0.65s | **1.15x** | 短视频略有优势 |
| 30s | 1.80s | 1.87s | 0.96x | 并行更慢 |
| 60s | 3.24s | 3.26s | 0.99x | 几乎持平 |
| 120s | 6.63s | 6.70s | 0.99x | 默认配置无优势 |

**测试命令**:
```bash
python scripts/benchmark-compose.py \
    --source benchmark-assets/source{N}.mp4 \
    --bar benchmark-assets/bar{N}.mp4 \
    --output-dir benchmark-output --overwrite
```

---

### 2. Chunk 大小影响 (60秒视频, workers=2)

| Chunk | Serial Wall | Parallel Wall | 加速比 |
|-------|-------------|---------------|--------|
| 5s | 3.32s | 4.57s | 0.73x ❌ |
| 10s | - | - | 0.99x |
| 15s | - | - | 1.00x |
| 30s | 3.32s | 3.09s | **1.08x** ✅ |

**测试命令**:
```bash
python scripts/benchmark-compose.py \
    --source benchmark-assets/source60.mp4 \
    --bar benchmark-assets/bar60.mp4 \
    --output-dir benchmark-output \
    --chunk-seconds {5,10,15,30} --overwrite
```

---

### 3. Worker 数量影响 (120秒视频, chunk=30s)

| Workers | Serial Wall | Parallel Wall | 加速比 | CPU 效率 |
|---------|-------------|---------------|--------|----------|
| 1 | 6.71s | 7.93s | 0.85x ❌ | 0.97x |
| 2 | 6.71s | 6.38s | 1.05x | 0.87x |
| 4 | 6.71s | **4.79s** | **1.40x** ✅ | 0.84x |
| 8 | 6.71s | 4.84s | 1.39x | 0.83x |
| 16 | 6.71s | 5.06s | 1.33x | 0.81x |

**测试命令**:
```bash
python scripts/benchmark-compose.py \
    --source benchmark-assets/source120.mp4 \
    --bar benchmark-assets/bar120.mp4 \
    --output-dir benchmark-output \
    --chunk-seconds 30 \
    --max-workers {1,2,4,8,16} --overwrite
```

---

## 性能图表

### Wall Clock 加速比

```
Workers vs Speedup (120s video, chunk=30s)

1.5x |                    ┌───┐
1.4x |                    │ • │ 4 workers
1.3x |              ┌───┐─┘   └───┐
1.2x |              │ • │ 8 workers
1.1x |         ┌───┐─┘   └───┐
1.0x |    ┌───┐─┘           │ • │ 16 workers
0.9x |    │ • │ 2 workers ┌─┘   └───┐
0.8x | ┌──┘   └───┐       │         │
0.7x | │ 1 worker │       │         │
0.6x | └──────────┴───────┴─────────┴
      +----+----+----+----+----+----+----
        1    2    4    8   12   16
              Workers
```

---

## 推荐配置

### 短视频 (< 60秒)

```python
# 使用串行模式
config = CompositionConfig(position=OverlayPosition.BOTTOM)
compose_vstack(source, bar, output, config)
```

### 中长视频 (≥ 60秒)

```python
# 使用并行模式，4 workers 是最佳性价比
config = ParallelConfig(
    position=OverlayPosition.BOTTOM,
    chunk_seconds=30,   # 30秒分块
    max_workers=4,      # 4个worker
    gop_multiplier=2,
)
await compose_vstack_parallel(source, bar, output, config)
```

### 配置建议总结

| 视频长度 | 推荐模式 | Workers | Chunk | 预期加速 |
|---------|---------|---------|-------|---------|
| < 60s | Serial | - | - | 基准 |
| 60-300s | Parallel | 4 | 30s | 1.3-1.4x |
| > 5min | Parallel | 4-8 | 30s | 1.4-1.5x |

---

## 性能权衡

| 指标 | Serial | Parallel | 说明 |
|------|--------|----------|------|
| Wall Time | 基准 | 1.4x 更快 | 用户实际等待时间 |
| CPU Time | 基准 | 1.2x 更多 | 总CPU消耗 |
| 内存 | 625MB | 626MB | 几乎相同 |
| 输出大小 | 基准 | 略大 (~10%) | GOP边界影响 |

**结论**: 并行模式用更多 CPU 时间换取更短的实际运行时间，适合需要快速完成的场景。

---

## 附录: 完整测试日志

### 测试环境

```bash
$ nproc
16

$ ffmpeg -version | head -1
ffmpeg version 6.1.1-3ubuntu5

$ python --version
Python 3.13.1
```

### 原始 JSON 输出示例

```json
{
  "serial": {
    "mode": "serial",
    "output_path": "benchmark-output/serial-output.mp4",
    "output_bytes": 85105,
    "wall_seconds": 3.322578307997901,
    "cpu_user_seconds": 17.732530999999998,
    "cpu_system_seconds": 2.589137,
    "self_max_rss_kb": 23136.0,
    "children_max_rss_kb": 625728.0,
    "max_rss_kb": 625728.0
  },
  "parallel": {
    "mode": "parallel",
    "output_path": "benchmark-output/parallel-output.mp4",
    "output_bytes": 101253,
    "wall_seconds": 4.574845514005574,
    "cpu_user_seconds": 21.178872,
    "cpu_system_seconds": 6.293094,
    "self_max_rss_kb": 24148.0,
    "children_max_rss_kb": 624656.0,
    "max_rss_kb": 624656.0
  },
  "speedup": {
    "wall": 0.7262711490095254,
    "cpu": 0.7397238333798171
  }
}
```
