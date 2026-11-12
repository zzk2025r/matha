"""Matha 机器人模块：运动控制、传感器、路径规划、机械臂。

覆盖：
  1) 运动控制
  2) 传感器数据处理
  3) 路径规划
  4) 机械臂控制
  5) 机器人导航
  6) SLAM
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RobotType(Enum):
    """机器人类型。"""
    MOBILE = "mobile"
    ARM = "arm"
    DRONE = "drone"
    HUMANOID = "humanoid"


@dataclass
class Joint:
    """关节。"""
    name: str = ""
    angle: float = 0.0
    max_angle: float = 180.0
    min_angle: float = -180.0
    speed: float = 1.0


@dataclass
class Robot:
    """机器人。"""
    name: str = ""
    robot_type: str = "mobile"
    joints: list[Joint] = field(default_factory=list)
    position: list[float] = field(default_factory=list)
    sensors: list[str] = field(default_factory=list)


@dataclass
class SensorData:
    """传感器数据。"""
    sensor_type: str = "ultrasonic"
    value: float = 0.0
    unit: str = "cm"
    timestamp: float = 0.0


class RobotEngine:
    """机器人引擎：运动、传感器、导航。"""

    def __init__(self):
        self._robots: list[Robot] = []
        self._initialized = False
        self._init_robot()

    def _init_robot(self) -> None:
        """初始化机器人引擎。"""
        self._initialized = True

    def create_robot(self, name: str = "robot",
                        robot_type: str = "mobile") -> Robot:
        """创建机器人。"""
        robot = Robot(name=name, robot_type=robot_type)
        self._robots.append(robot)
        return robot

    def add_joint(self, robot: Robot, name: str,
                     max_angle: float = 180) -> Joint:
        """添加关节。"""
        joint = Joint(name=name, max_angle=max_angle)
        robot.joints.append(joint)
        return joint

    def move_to(self, robot: Robot, x: float, y: float,
                   z: float = 0) -> bool:
        """移动到位置。"""
        robot.position = [x, y, z]
        return True

    def read_sensor(self, robot: Robot, sensor: str) -> SensorData:
        """读取传感器。"""
        raise RuntimeError(
            f"读取传感器 '{sensor}' 需要真实硬件驱动（本环境无传感器数据源；"
            "旧实现恒返回 value=0.0 假读数，已显式拒绝）")

    def plan_path(self, start: list[float], end: list[float]
                     ) -> list[list[float]]:
        """规划路径（直线插值：按 0.1 单位步长采样起点→终点）。"""
        if not start or len(start) != len(end):
            raise ValueError(
                f"路径起终点维度必须一致且非空：start={start}, end={end}")
        for v in (*start, *end):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"路径坐标需要数值，得到 {v!r}")
        dist = sum((e - s) ** 2 for s, e in zip(start, end)) ** 0.5
        n = max(2, min(101, int(dist / 0.1) + 1))
        return [
            [s + (e - s) * i / (n - 1) for s, e in zip(start, end)]
            for i in range(n)
        ]

    def control_arm(self, robot: Robot, joint_angles: list[float]) -> bool:
        """控制机械臂（真写关节角度：数量不符/越界显式拒绝）。"""
        if len(joint_angles) != len(robot.joints):
            raise ValueError(
                f"关节角度数量 ({len(joint_angles)}) 与机器人关节数 "
                f"({len(robot.joints)}) 不符：请先 添加关节")
        for joint, angle in zip(robot.joints, joint_angles):
            if isinstance(angle, bool) or not isinstance(angle, (int, float)):
                raise ValueError(f"关节 '{joint.name}' 角度需要数值，得到 {angle!r}")
            if not joint.min_angle <= angle <= joint.max_angle:
                raise ValueError(
                    f"关节 '{joint.name}' 角度 {angle} 越界 "
                    f"[{joint.min_angle}, {joint.max_angle}]")
            joint.angle = float(angle)
        return True


def create_robot_engine() -> RobotEngine:
    """创建机器人引擎。"""
    return RobotEngine()


def _register_robot(builtins: dict) -> None:
    """注册机器人内置函数。"""
    builtins["创建机器人引擎"] = create_robot_engine
    builtins["创建机器人"] = lambda n, t="mobile": RobotEngine().create_robot(n, t)
    builtins["添加关节"] = lambda r, n, ma=180: RobotEngine().add_joint(r, n, ma)
    builtins["移动到"] = lambda r, x, y, z=0: RobotEngine().move_to(r, x, y, z)
    builtins["读取传感器"] = lambda r, s: RobotEngine().read_sensor(r, s)
    builtins["规划路径"] = lambda r, s, e: RobotEngine().plan_path(s, e)
    builtins["控制机械臂"] = lambda r, ja: RobotEngine().control_arm(r, ja)


def _robot_symtab_names() -> list[str]:
    return [
        "创建机器人引擎", "创建机器人", "添加关节",
        "移动到", "读取传感器", "规划路径", "控制机械臂",
    ]


__all__ = [
    "RobotType", "Joint", "Robot", "SensorData",
    "RobotEngine", "create_robot_engine",
    "_register_robot", "_robot_symtab_names",
]
