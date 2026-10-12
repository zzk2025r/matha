"""Matha 可视化引擎 — 构建管线可视化、仪表盘、领域浏览器、性能图表。

覆盖：
  1) 构建管线可视化（.matha → MIR → 目标代码）
  2) 系统架构图
  3) 领域模块浏览器
  4) 编译状态仪表盘
  5) 性能统计图表
  6) 交互式Web仪表盘
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================
# 枚举与数据类
# ============================================================

class BuildStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    PENDING = "pending"


class TargetType(Enum):
    C = "C"
    PYTHON = "Python"
    LLVM = "LLVM"
    MATHA = "Matha"
    BINARY = "Binary"
    TRINARY = "Trinary"
    DECIMAL = "Decimal"
    WASM = "WASM"


@dataclass
class BuildStep:
    """构建步骤。"""
    name: str
    status: BuildStatus = BuildStatus.PENDING
    duration_ms: float = 0.0
    output: str = ""
    error: str = ""
    timestamp: float = 0.0

    def start(self):
        """开始步骤。"""
        self.status = BuildStatus.RUNNING
        self.timestamp = time.time()

    def complete(self, output: str = ""):
        """完成步骤。"""
        self.status = BuildStatus.SUCCESS
        self.duration_ms = (time.time() - self.timestamp) * 1000
        self.output = output

    def fail(self, error: str):
        """失败步骤。"""
        self.status = BuildStatus.FAILED
        self.duration_ms = (time.time() - self.timestamp) * 1000
        self.error = error


@dataclass
class PipelineResult:
    """管线结果。"""
    source: str = ""
    target: str = "c"
    steps: list[BuildStep] = field(default_factory=list)
    total_duration_ms: float = 0.0
    success: bool = False


# ============================================================
# 构建管线可视化
# ============================================================

class BuildPipelineVisualizer:
    """构建管线可视化器。

    展示 Matha 构建全流程：
    .matha → Lexer → Parser → Frontend → MIR → Opt → Backend → 目标代码
    """

    PIPELINE_STAGES = [
        ("Lexer", "词法分析", "🔤"),
        ("Parser", "语法分析", "📝"),
        ("Frontend", "前端IR", "⚙️"),
        ("MIR", "中间表示", "🔄"),
        ("Optimizer", "优化", "⚡"),
        ("Backend", "后端", "🎯"),
        ("CodeGen", "代码生成", "💻"),
        ("Linker", "链接", "🔗"),
    ]

    def __init__(self):
        self._steps: list[BuildStep] = []
        self._results: dict[str, PipelineResult] = {}
        self._start_time = time.time()

    def init_pipeline(self, source: str, target: str = "c") -> PipelineResult:
        """初始化构建管线。"""
        result = PipelineResult(source=source, target=target)
        for stage_name, stage_cn, _icon in self.PIPELINE_STAGES:
            result.steps.append(BuildStep(name=f"{stage_name} ({stage_cn})"))
        self._results[f"{source}:{target}"] = result
        return result

    def run_stage(self, result: PipelineResult, stage_idx: int, output: str = ""):
        """运行一个构建阶段。"""
        if stage_idx < len(result.steps):
            step = result.steps[stage_idx]
            step.start()
            # 模拟执行
            time.sleep(0.01)
            step.complete(output)

    def fail_stage(self, result: PipelineResult, stage_idx: int, error: str):
        """标记阶段失败。"""
        if stage_idx < len(result.steps):
            result.steps[stage_idx].fail(error)
            result.success = False

    def complete_pipeline(self, result: PipelineResult) -> PipelineResult:
        """完成整个管线。"""
        result.total_duration_ms = (time.time() - self._start_time) * 1000
        result.success = all(s.status == BuildStatus.SUCCESS for s in result.steps)
        return result

    def get_ascii_art(self, result: PipelineResult | None = None) -> str:
        """获取ASCII艺术管线图。"""
        if result is None:
            result = PipelineResult()

        lines = []
        lines.append("=" * 70)
        lines.append("  Matha 构建管线")
        lines.append("=" * 70)
        lines.append("")

        for i, (name, cn, icon) in enumerate(self.PIPELINE_STAGES):
            if i < len(result.steps):
                step = result.steps[i]
                status_icon = {
                    BuildStatus.SUCCESS: "✅",
                    BuildStatus.FAILED: "❌",
                    BuildStatus.RUNNING: "🔄",
                    BuildStatus.PENDING: "⏳",
                }.get(step.status, "❓")
                duration = f" ({step.duration_ms:.1f}ms)" if step.duration_ms > 0 else ""
                lines.append(f"  {icon} {status_icon} {name:12s} {cn:8s}{duration}")
            else:
                lines.append(f"  ⏳ {name:12s} {cn:8s}")

        lines.append("")
        lines.append(f"  目标: {result.target}")
        lines.append(f"  总耗时: {result.total_duration_ms:.1f}ms")
        lines.append(f"  状态: {'✅ 成功' if result.success else '❌ 失败'}")
        lines.append("=" * 70)
        return "\n".join(lines)

    def get_html_dashboard(self, result: PipelineResult | None = None) -> str:
        """获取HTML仪表盘。"""
        if result is None:
            result = PipelineResult()

        steps_html = ""
        for i, step in enumerate(result.steps):
            status_class = step.status.value
            icon = {
                "success": "✅",
                "failed": "❌",
                "running": "🔄",
                "pending": "⏳",
            }.get(status_class, "❓")
            steps_html += f"""
            <div class="pipeline-step {status_class}">
                <span class="step-icon">{icon}</span>
                <span class="step-name">{step.name}</span>
                <span class="step-duration">{step.duration_ms:.1f}ms</span>
            </div>"""

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Matha Build Pipeline</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }}
h1 {{ color: #00d4ff; text-align: center; }}
.pipeline {{ display: flex; flex-direction: column; gap: 8px; max-width: 600px; margin: 20px auto; }}
.pipeline-step {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px;
                   background: #16213e; border-radius: 8px; border-left: 4px solid #555; }}
.pipeline-step.success {{ border-left-color: #00ff88; }}
.pipeline-step.failed {{ border-left-color: #ff4444; }}
.pipeline-step.running {{ border-left-color: #ffaa00; animation: pulse 1s infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
.step-icon {{ font-size: 20px; }}
.step-name {{ flex: 1; font-weight: 600; }}
.step-duration {{ color: #888; font-size: 12px; }}
.status {{ text-align: center; margin-top: 20px; font-size: 24px; }}
.target {{ text-align: center; color: #00d4ff; }}
</style></head><body>
<h1>🧮 Matha Build Pipeline</h1>
<div class="target">目标: {result.target}</div>
<div class="status">{'✅ 成功' if result.success else '❌ 失败'}</div>
<div class="pipeline">{steps_html}</div>
</body></html>"""


# ============================================================
# 领域模块浏览器
# ============================================================

class DomainBrowser:
    """领域模块浏览器。"""

    CATEGORY_COLORS = {
        "general": "#00d4ff",
        "science": "#4ecca3",
        "engineering": "#ffaa00",
        "creative": "#ff6b6b",
        "frontier": "#c084fc",
    }

    def __init__(self, registry: Any = None):
        self.registry = registry

    def get_html(self) -> str:
        """获取HTML领域浏览器。"""
        if not self.registry:
            return "<p>无领域注册表</p>"

        domains = self.registry.list_domains()
        domain_cards = ""
        for d in domains:
            color = self.CATEGORY_COLORS.get(d.get("category", "general"), "#888")
            domain_cards += f"""
            <div class="domain-card" style="border-color: {color}">
                <h3 style="color: {color}">{d['name']}</h3>
                <p>{d['name']}</p>
                <span class="category">{d.get('category', 'general')}</span>
                <span class="functions">{d['functions']} 函数</span>
                <span class="targets">{', '.join(d.get('targets', []))}</span>
            </div>"""

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Matha Domain Browser</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
h1 {{ color: #00d4ff; text-align: center; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 16px; }}
.domain-card {{ background: #16213e; border: 2px solid #555; border-radius: 12px; padding: 16px; }}
.domain-card h3 {{ margin: 0 0 8px; font-size: 14px; }}
.category {{ background: #333; padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
.functions {{ color: #4ecca3; font-size: 12px; }}
.targets {{ color: #888; font-size: 11px; margin-top: 4px; }}
.stats {{ text-align: center; margin-bottom: 20px; }}
</style></head><body>
<h1>📚 Matha 领域模块浏览器</h1>
<div class="stats">{len(domains)} 个领域模块</div>
<div class="grid">{domain_cards}</div>
</body></html>"""


# ============================================================
# 性能仪表盘
# ============================================================

@dataclass
class PerfDataPoint:
    """性能数据点。"""
    timestamp: float
    eval_time_ms: float
    compile_time_ms: float
    cache_hits: int
    cache_misses: int


class PerformanceDashboard:
    """性能仪表盘。"""

    def __init__(self):
        self._data: list[PerfDataPoint] = []
        self._start_time = time.time()

    def record(self, eval_time_ms: float = 0, compile_time_ms: float = 0,
               cache_hits: int = 0, cache_misses: int = 0):
        """记录性能数据。"""
        self._data.append(PerfDataPoint(
            timestamp=time.time() - self._start_time,
            eval_time_ms=eval_time_ms,
            compile_time_ms=compile_time_ms,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        ))

    def get_stats(self) -> dict:
        """获取统计摘要。"""
        if not self._data:
            return {"count": 0}
        total_evals = sum(d.eval_time_ms for d in self._data)
        total_compiles = sum(d.compile_time_ms for d in self._data)
        total_hits = sum(d.cache_hits for d in self._data)
        total_misses = sum(d.cache_misses for d in self._data)
        return {
            "count": len(self._data),
            "total_eval_ms": total_evals,
            "total_compile_ms": total_compiles,
            "total_cache_hits": total_hits,
            "total_cache_misses": total_misses,
            "avg_eval_ms": total_evals / len(self._data) if self._data else 0,
            "avg_compile_ms": total_compiles / len(self._data) if self._data else 0,
            "hit_rate": total_hits / (total_hits + total_misses + 1) * 100,
        }

    def get_html(self) -> str:
        """获取HTML性能仪表盘。"""
        stats = self.get_stats()
        data_points = ", ".join(str(d.eval_time_ms) for d in self._data[-50:])
        compile_points = ", ".join(str(d.compile_time_ms) for d in self._data[-50:])
        ", ".join(str(d.cache_hits / (d.cache_hits + d.cache_misses + 1) * 100) for d in self._data[-50:])

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Matha Performance Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
h1 {{ color: #00d4ff; text-align: center; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
.metric {{ background: #16213e; padding: 20px; border-radius: 12px; text-align: center; }}
.metric-value {{ font-size: 28px; color: #00d4ff; font-weight: bold; }}
.metric-label {{ color: #888; font-size: 12px; margin-top: 4px; }}
.chart-container {{ background: #16213e; padding: 16px; border-radius: 12px; margin: 16px 0; }}
</style></head><body>
<h1>📊 Matha 性能仪表盘</h1>
<div class="grid">
  <div class="metric"><div class="metric-value">{stats.get('count', 0)}</div><div class="metric-label">运行次数</div></div>
  <div class="metric"><div class="metric-value">{stats.get('avg_eval_ms', 0):.2f}ms</div><div class="metric-label">平均评估</div></div>
  <div class="metric"><div class="metric-value">{stats.get('avg_compile_ms', 0):.2f}ms</div><div class="metric-label">平均编译</div></div>
  <div class="metric"><div class="metric-value">{stats.get('hit_rate', 0):.1f}%</div><div class="metric-label">缓存命中率</div></div>
</div>
<div class="chart-container"><canvas id="evalChart"></canvas></div>
<div class="chart-container"><canvas id="compileChart"></canvas></div>
<script>
const evalData = [{data_points}];
const compileData = [{compile_points}];
new Chart(document.getElementById('evalChart'), {{type:'line', data:{{labels:evalData.map((_,i)=>i), datasets:[{{label:'Eval ms', data:evalData, borderColor:'#00d4ff'}}]}}}});
new Chart(document.getElementById('compileChart'), {{type:'line', data:{{labels:compileData.map((_,i)=>i), datasets:[{{label:'Compile ms', data:compileData, borderColor:'#4ecca3'}}]}}}});
</script></body></html>"""


# ============================================================
# 系统架构图
# ============================================================

class ArchitectureVisualizer:
    """系统架构可视化。"""

    def get_ascii(self) -> str:
        """ASCII架构图。"""
        return """
╔═══════════════════════════════════════════════════════════════╗
║                    Matha v4.5 架构图                          ║
╠═══════════════════════════════════════════════════════════════╣
║                                                             ║
║  ┌─────────────────────────────────────────────────┐        ║
║  │              MathaSystem (统一入口)               │        ║
║  └─────────────────────────────────────────────────┘        ║
║                          │                                  ║
║          ┌───────────────┼───────────────┐                  ║
║          │               │               │                  ║
║  ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐         ║
║  │  核心引擎层   │ │ 虚拟代码引擎 │ │ 自举编译器   │         ║
║  │  Interpreter │ │ Registry    │ │ Bootstrap   │         ║
║  │  Compiler    │ │ Engine      │ │ matha2c     │         ║
║  │  VM          │ │ Definition  │ │ NumberSys   │         ║
║  │  Runtime     │ │             │ │             │         ║
║  └───────┬──────┘ └──────┬──────┘ └──────┬──────┘         ║
║          │               │               │                  ║
║  ┌───────▼───────────────▼───────────────▼──────┐          ║
║  │            63个领域模块                        │          ║
║  │  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐   │          ║
║  │  │游戏  ││图形  ││办公  ││操作系统││网络  │   │          ║
║  │  │引擎  ││引擎  ││文档  ││模块  ││模块  │   │          ║
║  │  └──────┘└──────┘└──────┘└──────┘└──────┘   │          ║
║  │  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐   │          ║
║  │  │IO    ││时间  ││AI    ││LSP   ││MCP   │   │          ║
║  │  │系统  ││模块  ││助手  ││服务器││服务器│   │          ║
║  │  └──────┘└──────┘└──────┘└──────┘└──────┘   │          ║
║  └──────────────────────────────────────────────┘          ║
║                          │                                  ║
║  ┌───────────────────────▼──────────────────────────┐      ║
║  │  编译目标                                       │      ║
║  │  C / Python / LLVM / Matha / Base-2/3/10 / WASM  │      ║
║  └──────────────────────────────────────────────────┘      ║
║                                                             ║
╚═══════════════════════════════════════════════════════════════╝
"""

    def get_html(self) -> str:
        """获取HTML架构图。"""
        return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Matha Architecture</title>
<style>
body { font-family: 'Segoe UI', sans-serif; background: #0a0a1a; color: #eee; padding: 20px; }
h1 { color: #00d4ff; text-align: center; }
.layer { border: 2px solid #333; border-radius: 12px; padding: 16px; margin: 8px; background: #111827; }
.layer-title { color: #00d4ff; font-weight: bold; margin-bottom: 8px; }
.engine-row { display: flex; gap: 12px; flex-wrap: wrap; }
.engine-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; flex: 1; min-width: 120px; text-align: center; }
.engine-card .icon { font-size: 24px; }
.engine-card .name { color: #00d4ff; font-weight: bold; }
.domain-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.domain-item { background: #1e293b; border-radius: 6px; padding: 8px; text-align: center; font-size: 12px; }
.target-bar { background: #1e293b; border-radius: 8px; padding: 12px; text-align: center; }
.target-item { display: inline-block; background: #00d4ff; color: #000; padding: 4px 12px; margin: 4px; border-radius: 4px; font-weight: bold; }
</style></head><body>
<h1>🧮 Matha v4.5 架构图</h1>
<div class="layer">
  <div class="layer-title">🎯 MathaSystem (统一入口)</div>
  <div class="engine-row">
    <div class="engine-card"><div class="icon">🔤</div><div class="name">Lexer</div></div>
    <div class="engine-card"><div class="icon">📝</div><div class="name">Parser</div></div>
    <div class="engine-card"><div class="icon">⚙️</div><div class="name">Frontend</div></div>
    <div class="engine-card"><div class="icon">🔄</div><div class="name">MIR</div></div>
    <div class="engine-card"><div class="icon">⚡</div><div class="name">Optimizer</div></div>
    <div class="engine-card"><div class="icon">🎯</div><div class="name">Backend</div></div>
    <div class="engine-card"><div class="icon">💻</div><div class="name">CodeGen</div></div>
  </div>
</div>
<div class="layer">
  <div class="layer-title">📚 63个领域模块</div>
  <div class="domain-grid">
    <div class="domain-item">🎮 游戏引擎</div>
    <div class="domain-item">🎨 图形引擎</div>
    <div class="domain-item">📄 办公文档</div>
    <div class="domain-item">⚙️ 操作系统</div>
    <div class="domain-item">🌐 网络通信</div>
    <div class="domain-item">📁 文件系统</div>
    <div class="domain-item">💾 IO系统</div>
    <div class="domain-item">⏰ 时间模块</div>
    <div class="domain-item">🤖 AI助手</div>
    <div class="domain-item">📡 LSP服务器</div>
    <div class="domain-item">🔌 MCP服务器</div>
    <div class="domain-item">📊 54+ 领域</div>
  </div>
</div>
<div class="layer">
  <div class="layer-title">🎯 编译目标</div>
  <div class="target-bar">
    <span class="target-item">C</span>
    <span class="target-item">Python</span>
    <span class="target-item">LLVM</span>
    <span class="target-item">Matha</span>
    <span class="target-item">Base-2</span>
    <span class="target-item">Base-3</span>
    <span class="target-item">Base-10</span>
    <span class="target-item">WASM</span>
  </div>
</div>
</body></html>"""


# ============================================================
# 可视化引擎（统一入口）
# ============================================================

class MathaVisualizer:
    """Matha 可视化引擎。

    提供完整的构建可视化能力：
    - 构建管线可视化
    - 系统架构图
    - 领域模块浏览器
    - 性能仪表盘
    - 交互式Web界面
    """

    def __init__(self, system: Any = None):
        self.system = system
        self.pipeline = BuildPipelineVisualizer()
        self.browser = DomainBrowser()
        self.perf = PerformanceDashboard()
        self.arch = ArchitectureVisualizer()
        self._dashboard_path = str(Path(__file__).parent.parent / "matha_dashboard")

    def visualize_pipeline(self, source: str, target: str = "c") -> str:
        """可视化构建管线。"""
        result = self.pipeline.init_pipeline(source, target)
        for i in range(len(self.pipeline.PIPELINE_STAGES)):
            self.pipeline.run_stage(result, i, f"Stage {i} complete")
        self.pipeline.complete_pipeline(result)
        return self.pipeline.get_ascii_art(result)

    def visualize_architecture(self) -> str:
        """可视化系统架构。"""
        return self.arch.get_ascii()

    def visualize_domains(self) -> str:
        """可视化领域模块。"""
        if self.system and self.system.domain_registry:
            self.browser.registry = self.system.domain_registry
        return self.browser.get_html()

    def visualize_performance(self) -> str:
        """可视化性能。"""
        return self.perf.get_html()

    def save_dashboard(self, path: str = None) -> str:
        """保存完整仪表盘到HTML文件。"""
        if path is None:
            path = self._dashboard_path
        os.makedirs(path, exist_ok=True)
        html_path = os.path.join(path, "index.html")
        full_html = self._generate_full_dashboard()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        return html_path

    def _generate_full_dashboard(self) -> str:
        """生成完整仪表盘HTML。"""
        pipeline_result = self.pipeline.init_pipeline("result = 1 + 2 * 3", "c")
        for i in range(len(self.pipeline.PIPELINE_STAGES)):
            self.pipeline.run_stage(pipeline_result, i)
        self.pipeline.complete_pipeline(pipeline_result)

        pipeline_html = self.pipeline.get_html_dashboard(pipeline_result)
        arch_html = self.arch.get_html()

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Matha v4.5 Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', sans-serif; background: #0a0a1a; color: #eee; }}
nav {{ background: #1a1a2e; padding: 12px 20px; display: flex; gap: 16px; border-bottom: 2px solid #00d4ff; }}
nav a {{ color: #00d4ff; text-decoration: none; padding: 8px 16px; border-radius: 6px; }}
nav a:hover {{ background: #16213e; }}
section {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #00d4ff; text-align: center; margin: 20px 0; }}
.card {{ background: #16213e; border-radius: 12px; padding: 20px; margin: 16px 0; }}
.card h2 {{ color: #4ecca3; }}
</style></head><body>
<nav>
  <a href="#pipeline">构建管线</a>
  <a href="#architecture">架构</a>
  <a href="#domains">领域</a>
  <a href="#performance">性能</a>
</nav>
<section id="pipeline">
  <h1>🧮 Matha v4.5 Dashboard</h1>
  <div class="card"><h2>📊 构建管线</h2>{pipeline_html}</div>
</section>
<section id="architecture">
  <div class="card"><h2>🏗️ 系统架构</h2>{arch_html}</div>
</section>
<section id="domains">
  <div class="card"><h2>📚 领域模块</h2><iframe src="about:blank" id="domainFrame" style="width:100%;height:600px;border:none;"></iframe></div>
</section>
<section id="performance">
  <div class="card"><h2>📈 性能仪表盘</h2><iframe src="about:blank" id="perfFrame" style="width:100%;height:600px;border:none;"></iframe></div>
</section>
<script>
document.getElementById('domainFrame').srcdoc = `{self.browser.get_html()}`;
document.getElementById('perfFrame').srcdoc = `{self.perf.get_html()}`;
</script></body></html>"""


# ============================================================
# 全局实例
# ============================================================

_global_visualizer: MathaVisualizer | None = None


def get_visualizer(system: Any = None) -> MathaVisualizer:
    """获取全局可视化引擎。"""
    global _global_visualizer
    if _global_visualizer is None:
        _global_visualizer = MathaVisualizer(system)
    return _global_visualizer


def reset_visualizer():
    """重置全局可视化引擎。"""
    global _global_visualizer
    _global_visualizer = None
