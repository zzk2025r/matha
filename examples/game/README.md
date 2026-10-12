# 游戏开发示例

## 1. 简单的球体弹跳游戏

```matha
# 创建游戏引擎
engine = create_game_engine()

# 创建场景
scene = create_scene("bounce")

# 创建玩家实体
player = create_entity("ball")
add_collider(player, 20, 20)
add_rigidbody(player, mass=1.0)
set_position(player, 400, 300)

# 添加重力
apply_force(player, 0, -9.8)

# 启动游戏
start_engine(engine)
```

## 2. 粒子效果

```matha
# 创建粒子系统
ps = create_particle_system(max_particles=1000)

# 发射粒子
emit_particles(ps, Color.red, speed=500.0)

# 更新粒子
update_particles(ps, dt=0.016)
```

## 3. 2D 平台游戏

```matha
# 创建关卡
level_manager = create_level_manager()
load_level(level_manager, "level1")

# 创建玩家
player = create_entity("player")
add_collider(player, 32, 64)
add_rigidbody(player, mass=1.0)

# 添加平台
platform = create_entity("platform")
add_collider(platform, 256, 32)
set_position(platform, 0, 500)
```

## 4. 物理模拟

```matha
# 创建物理世界
world = PhysicsWorld(gravity=Vec2(0, -9.8))

# 添加多个刚体
for i in range(10):
    body = RigidBody(velocity=Vec2(0, 0))
    body.position = Vec2(i * 50, 500)
    world.add_body(body)

# 物理步进
world.step(0.016)
```

## 5. 关卡管理

```matha
# 创建关卡管理器
lm = create_level_manager()

# 加载关卡
load_level(lm, "level1")

# 下一关
next_level(lm)
```

---

*Matha v4.5 | 游戏开发示例*