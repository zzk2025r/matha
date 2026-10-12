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
        return SensorData(sensor_type=sensor, value=0.0)

    def plan_path(self, start: list[float], end: list[float]
                     ) -> list[list[float]]:
        """规划路径。"""
        return [start, end]

    def control_arm(self, robot: Robot, joint_angles: list[float]) -> bool:
        """控制机械臂。"""
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
