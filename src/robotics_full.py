"""Matha 机器人引擎：位姿数学 + PID 控制 + 虚拟状态机。

能力边界（阶段 22a 假成功清算）：真实可用面——Pose 旋转矩阵、
PID 控制器、正运动学（简化链式）、关节状态与轨迹时间插值、
夹爪开合状态机。凡需要真实硬件或求解器的面一律显式拒绝，
不再伪造：逆运动学（曾恒返全零）、路径规划（曾无视障碍物
返回起终点）、SLAM 更新/定位（曾无视扫描）、传感器读取
（曾伪造空读数）、抓取（曾假 True）、机器人连接。
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RobotType(Enum):
    MOBILE = "mobile"
    ARM = "arm"
    DRONE = "drone"
    HUMANOID = "humanoid"
    INDUSTRIAL = "industrial"


class JointType(Enum):
    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    FIXED = "fixed"
    CONTINUOUS = "continuous"
    UNIVERSAL = "universal"


class SensorType(Enum):
    LIDAR = "lidar"
    CAMERA = "camera"
    IMU = "imu"
    GPS = "gps"
    ULTRASONIC = "ultrasonic"
    ENCODER = "encoder"
    FORCE_TORQUE = "force_torque"
    PROXIMITY = "proximity"
    DEPTH = "depth"
    RADAR = "radar"


class MotionPlannerType(Enum):
    RRT = "rrt"
    RRT_STAR = "rrt_star"
    PRM = "prm"
    A_STAR = "a_star"
    D_STAR = "d_star"
    HYBRID_A_STAR = "hybrid_a_star"
    OMPL = "ompl"


@dataclass
class Joint:
    name: str = "joint"
    joint_type: JointType = JointType.REVOLUTE
    position: float = 0.0
    velocity: float = 0.0
    effort: float = 0.0
    lower_limit: float = -math.pi
    upper_limit: float = math.pi


@dataclass
class Link:
    name: str = "link"
    mass: float = 1.0
    inertia: tuple[float, float, float, float, float, float] = (0, 0, 0, 0, 0, 0)
    origin: tuple[float, float, float] = (0, 0, 0)
    joints: list[Joint] = field(default_factory=list)


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def to_matrix(self) -> list[list[float]]:
        cx, cy, cz = math.cos(self.roll), math.cos(self.pitch), math.cos(self.yaw)
        sx, sy, sz = math.sin(self.roll), math.sin(self.pitch), math.sin(self.yaw)
        return [
            [cy*cz, -cy*sz, sy, self.x],
            [cx*sz+sx*sy*cz, cx*cz-sx*sy*sz, -sx, self.y],
            [sx*sz-cx*sy*cz, sx*cz+cx*sy*sz, cx, self.z],
            [0, 0, 0, 1],
        ]


@dataclass
class Twist:
    linear: tuple[float, float, float] = (0, 0, 0)
    angular: tuple[float, float, float] = (0, 0, 0)


@dataclass
class OccupancyGrid:
    width: int = 100
    height: int = 100
    resolution: float = 0.05
    data: list[int] = field(default_factory=list)
    origin: Pose = field(default_factory=Pose)


@dataclass
class SensorReading:
    data: list[Any] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frequency: float = 0.0
    type: str = ""


class Robot:
    """机器人。"""

    def __init__(self, name: str = "robot",
                 robot_type: RobotType = RobotType.MOBILE):
        self.name = name
        self.robot_type = robot_type
        self.joints: list[Joint] = []
        self.links: list[Link] = []
        self.pose = Pose()
        self.twist = Twist()
        self._sensors: dict[str, Any] = {}
        self._actuators: dict[str, Any] = {}
        self._connected = False
        self._speed = 0.0

    def add_joint(self, joint: Joint) -> None:
        self.joints.append(joint)

    def add_link(self, link: Link) -> None:
        self.links.append(link)

    def forward_kinematics(self) -> list[Pose]:
        poses = []
        for joint in self.joints:
            poses.append(Pose(
                x=self.pose.x + joint.position * math.cos(self.pose.yaw),
                y=self.pose.y + joint.position * math.sin(self.pose.yaw),
                z=self.pose.z,
            ))
        return poses

    def inverse_kinematics(self, target: Pose) -> list[float]:
        raise NotImplementedError(
            "逆运动学求解器未实现（不再返回全零关节角）")

    def set_joint_positions(self, positions: list[float]) -> None:
        for i, pos in enumerate(positions):
            if i < len(self.joints):
                self.joints[i].position = pos

    def connect(self) -> None:
        raise NotImplementedError(
            "连接真实机器人需要硬件后端，未实现")

    def disconnect(self) -> None:
        self._connected = False

    def step(self, dt: float) -> None:
        self.pose.x += self.twist.linear[0] * dt
        self.pose.y += self.twist.linear[1] * dt
        self.pose.z += self.twist.linear[2] * dt


class MotionPlanner:
    """运动规划器。"""

    def __init__(self, planner_type: MotionPlannerType = MotionPlannerType.RRT):
        self.planner_type = planner_type
        self._path: list[Pose] = []
        self._obstacles: list[Pose] = []

    def plan(self, start: Pose, goal: Pose
                ) -> list[Pose]:
        raise NotImplementedError(
            "路径规划需要真实规划器（曾无视障碍物返回起终点），未实现")

    def add_obstacle(self, pose: Pose) -> None:
        self._obstacles.append(pose)

    def get_path(self) -> list[Pose]:
        return self._path

    def smooth_path(self) -> list[Pose]:
        raise NotImplementedError("路径平滑需要真实规划器，未实现")


class SLAM:
    """同步定位与建图。"""

    def __init__(self, grid: OccupancyGrid):
        self.grid = grid
        self._map: dict[str, Any] = {}
        self._pose = Pose()
        self._particles: list[Pose] = []

    def update(self, scan: list[float],
                  pose: Pose) -> OccupancyGrid:
        raise NotImplementedError("SLAM 建图需要真实激光/视觉后端，未实现")

    def get_map(self) -> OccupancyGrid:
        return self.grid

    def localize(self, scan: list[float]) -> Pose:
        raise NotImplementedError("SLAM 定位需要真实激光/视觉后端，未实现")


class SensorDriver:
    """传感器驱动。"""

    def __init__(self, sensor_type: SensorType, name: str = "sensor"):
        self.sensor_type = sensor_type
        self.name = name
        self._reading: SensorReading = {}
        self._connected = False

    def read(self) -> SensorReading:
        raise NotImplementedError(
            "传感器读取需要真实硬件，未实现（不再伪造空读数）")

    def calibrate(self) -> bool:
        raise NotImplementedError("传感器校准需要真实硬件，未实现")

    def set_frequency(self, freq: float) -> None:
        self._reading["frequency"] = freq


class Controller:
    """控制器。"""

    def __init__(self, type: str = "pid"):
        self.type = type
        self._kp = 1.0
        self._ki = 0.0
        self._kd = 0.0
        self._integral = 0.0
        self._prev_error = 0.0

    def compute(self, error: float, dt: float) -> float:
        self._integral += error * dt
        derivative = (error - self._prev_error) / dt if dt > 0 else 0
        output = self._kp * error + self._ki * self._integral + self._kd * derivative
        self._prev_error = error
        return output

    def set_gains(self, kp: float, ki: float, kd: float) -> None:
        self._kp = kp
        self._ki = ki
        self._kd = kd


class Trajectory:
    """轨迹。"""

    def __init__(self, waypoints: list[Pose] = None):
        self.waypoints = waypoints or []
        self._time: list[float] = []
        self._velocity: list[Twist] = []

    def add_waypoint(self, pose: Pose, t: float = 0.0) -> None:
        self.waypoints.append(pose)
        self._time.append(t)

    def get_waypoint(self, t: float) -> Pose:
        if not self.waypoints:
            return Pose()
        if len(self._time) != len(self.waypoints):
            return self.waypoints[0]
        if len(self.waypoints) == 1 or t <= self._time[0]:
            return self.waypoints[0]
        if t >= self._time[-1]:
            return self.waypoints[-1]
        for i in range(len(self.waypoints) - 1):
            t0, t1 = self._time[i], self._time[i + 1]
            if t0 <= t <= t1:
                if t1 == t0:
                    return self.waypoints[i]
                f = (t - t0) / (t1 - t0)
                a, b = self.waypoints[i], self.waypoints[i + 1]
                return Pose(
                    x=a.x + (b.x - a.x) * f,
                    y=a.y + (b.y - a.y) * f,
                    z=a.z + (b.z - a.z) * f,
                    roll=a.roll + (b.roll - a.roll) * f,
                    pitch=a.pitch + (b.pitch - a.pitch) * f,
                    yaw=a.yaw + (b.yaw - a.yaw) * f,
                )
        return self.waypoints[-1]

    def get_duration(self) -> float:
        return self._time[-1] if self._time else 0.0


class Gripper:
    """夹爪。"""

    def __init__(self, name: str = "gripper"):
        self.name = name
        self.open = True
        self._force = 0.0
        self._position = 0.0

    def open_gripper(self) -> None:
        self.open = True
        self._position = 1.0

    def close_gripper(self) -> None:
        self.open = False
        self._position = 0.0

    def set_force(self, force: float) -> None:
        self._force = force

    def grasp(self) -> bool:
        raise NotImplementedError("抓取需要真实夹爪硬件，未实现")

    def release(self) -> None:
        self.open_gripper()


class RobotArm(Robot):
    """机械臂。"""

    def __init__(self, name: str = "arm",
                 dof: int = 6):
        super().__init__(name=name, robot_type=RobotType.ARM)
        self.dof = dof
        self.gripper = Gripper()
        self._joint_angles = [0.0] * dof

    def move_to(self, pose: Pose) -> list[float]:
        angles = self.inverse_kinematics(pose)
        self.set_joint_positions(angles)
        return angles

    def plan_motion(self, start: Pose, end: Pose) -> list[Pose]:
        raise NotImplementedError(
            "机械臂运动规划需要真实规划器，未实现")


def create_robot(name: str = "robot",
                    robot_type: RobotType = RobotType.MOBILE
                    ) -> Robot:
    return Robot(name=name, robot_type=robot_type)


def create_motion_planner(planner_type: MotionPlannerType = MotionPlannerType.RRT
                             ) -> MotionPlanner:
    return MotionPlanner(planner_type=planner_type)


def create_slam(grid: OccupancyGrid) -> SLAM:
    return SLAM(grid=grid)


def create_sensor_driver(sensor_type: SensorType,
                            name: str = "sensor") -> SensorDriver:
    return SensorDriver(sensor_type=sensor_type, name=name)


def create_controller(type: str = "pid") -> Controller:
    return Controller(type=type)


def create_trajectory() -> Trajectory:
    return Trajectory()


def create_gripper(name: str = "gripper") -> Gripper:
    return Gripper(name=name)


# ============================================================
# 内置注册
# ============================================================

def _register_robotics(builtins: dict) -> None:
    builtins["创建机器人"] = create_robot
    builtins["创建运动规划器"] = create_motion_planner
    builtins["创建SLAM"] = create_slam
    builtins["创建传感器驱动"] = create_sensor_driver
    builtins["创建控制器"] = create_controller
    builtins["创建轨迹"] = create_trajectory
    builtins["创建夹爪"] = create_gripper


def _robotics_names() -> list[str]:
    return ["创建机器人", "创建运动规划器",
            "创建SLAM", "创建传感器驱动",
            "创建控制器", "创建轨迹",
            "创建夹爪"]


__all__ = [
    "RobotType", "JointType", "SensorType",
    "MotionPlannerType",
    "Joint", "Link", "Pose", "Twist",
    "OccupancyGrid", "SensorReading",
    "Robot", "MotionPlanner", "SLAM",
    "SensorDriver", "Controller",
    "Trajectory", "Gripper", "RobotArm",
    "create_robot", "create_motion_planner",
    "create_slam", "create_sensor_driver",
    "create_controller", "create_trajectory",
    "create_gripper",
    "_register_robotics", "_robotics_names",
]
