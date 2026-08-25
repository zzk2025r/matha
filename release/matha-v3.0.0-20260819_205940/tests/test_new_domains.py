# -*- coding: utf-8 -*-
"""Matha 领域注册测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.interp import _build_domain_builtins

b = _build_domain_builtins()

new_domains = [
    ("automation", ["PLC扫描周期", "传感器采样率", "执行器响应时间", "时序约束满足", "自动化流程效率", "异常检测率"]),
    ("iot_hardware", ["MQTT消息大小", "传感器覆盖半径", "边缘延迟", "设备在线率", "数据聚合效率", "功耗预算"]),
    ("os_network", ["进程调度等待", "内存页表开销", "文件碎片率", "TCP重传率", "DNS查询延迟", "带宽利用率"]),
    ("audio_video", ["音频采样率转换", "视频码率估算", "流媒体延迟", "编解码压缩比", "音频信噪比", "视频帧率稳定性"]),
    ("graphics", ["齐次变换矩阵", "投影变换", "裁剪区域", "光栅化点数", "颜色空间转换", "抗锯齿系数"]),
    ("hpc", ["Amdahl加速比", "并行效率", "通信延迟估算", "负载均衡度", "内存带宽利用率", "浮点运算峰值"]),
    ("fintech", ["BlackScholes期权定价", "VaR风险价值", "夏普比率", "信用评分", "流动性覆盖率", "杠杆率"]),
    ("autonomous", ["碰撞时间估算", "路径规划复杂度", "传感器融合误差", "决策响应时间", "定位精度", "油耗估算"]),
    ("aerospace", ["轨道速度计算", "推进剂消耗率", "结构强度系数", "热防护质量", "再入角估算", "比冲"]),
    ("bio_computing", ["GC含量计算", "分子质量估算", "蛋白折叠能量", "序列比对得分", "系统稳定性", "代谢通量"]),
    ("hardware_reverse", ["信号频率分析", "协议解析率", "固件完整性校验", "逆向复杂度", "时钟频率估算", "功耗分析"]),
    ("spatial_meta", ["空间索引效率", "元数据查询延迟", "地理编码精度", "坐标变换误差", "边界框交集", "缓冲区分析"]),
    ("algo_trading", ["策略夏普比率", "最大回撤估算", "订单执行成本", "滑点估算", "波动率预测", "相关性矩阵"]),
    ("comp_chem", ["分子轨道能量", "反应活化能", "键长计算", "振动频率", "热力学稳定性", "溶剂化能"]),
    ("green_tech", ["碳足迹估算", "能源效率", "太阳能转化率", "风力发电系数", "电池循环寿命", "减排量计算"]),
    ("metaverse_arch", ["渲染帧率估算", "物理模拟步长", "碰撞检测复杂度", "用户并发数", "资产加载延迟", "网络同步延迟"]),
    ("digital_rights", ["水印嵌入强度", "版权保护指数", "访问控制粒度", "哈希碰撞概率", "密钥轮换周期", "数字指纹"]),
]

failures = []
for domain, keys in new_domains:
    for key in keys:
        if key not in b:
            failures.append(f"{domain}/{key}")

if failures:
    print(f"FAIL: {len(failures)} 函数未注册:")
    for f in failures:
        print(f"  ✗ {f}")
    sys.exit(1)
else:
    print(f"全部 {len(new_domains)} 个新领域注册验证通过 ✓")
    print(f"新注册函数总数: {len(new_domains) * 6}")
