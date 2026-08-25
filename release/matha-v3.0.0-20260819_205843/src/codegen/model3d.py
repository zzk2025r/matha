# -*- coding: utf-8 -*-
"""Model3DGenerator：把 Matha 规格编译为 Three.js 3D 模型场景。

建模与游戏同属「交互式可视化」体系：
  - 游戏 = 动态 2D 交互场景（GameGenerator，Canvas + 游戏循环）
  - 建模 = 静态/动画 3D 场景展示（Model3DGenerator，Three.js + WebGL）

输出文件：
  - index.html  可直接双击运行的 Three.js 3D 场景（CDN 加载 Three.js）

建模规格元素（通过 AppSpec.elements 传入）：
  立方体（box/cube）       ：参数 size/w/h/d
  球体（sphere/ball）      ：参数 r
  圆柱（cylinder）         ：参数 r/h
  圆锥（cone）             ：参数 r/h
  圆环（torus）            ：参数 r/tube
  平面（plane）            ：参数 w/h
  齿轮（gear）             ：参数 r/teeth
  建筑（building）         ：参数 w/h/d/floors
  光源（light）            ：参数 type/color/intensity
  相机（camera）           ：参数 x/y/z/fov
  文字（h1/p/text）        ：页面 UI 文字

额外字段（meta）：
  背景 = "#1a1a2e"        场景背景色
  动画 = "旋转"           旋转/弹跳/自转/无
  材质 = "金属"           金属/玻璃/标准/线框
  颜色 = "#e94560"        默认材质颜色
  轨道控制 = "是"         是否启用鼠标轨道控制（OrbitControls）

支持：
  - 参数化几何体（10+ 种）
  - 材质系统（MeshStandard/MeshPhysical/线框）
  - 光照（环境光/方向光/点光）
  - 透视相机 + 轨道控制
  - 动画（旋转/弹跳/自转）
  - 多对象组合场景
"""

from __future__ import annotations
from src.codegen.base import Generator, CodegenResult, Element


class Model3DGenerator(Generator):
    """3D 建模生成器：AppSpec → Three.js WebGL 场景。"""

    def generate(self) -> CodegenResult:
        try:
            html = self._build_html()
            path = self._write("index.html", html)
        except Exception as e:
            return CodegenResult(成功=False, 类型="建模", 名称=self.app.name,
                                 错误=str(e))
        return CodegenResult(
            成功=True, 类型="建模", 名称=self.app.name,
            文件=[path], 入口=path,
        )

    def _build_html(self) -> str:
        title = self.app.title or self.app.name
        bg = self.app.meta.get("背景", "#1a1a2e")
        animation = self.app.meta.get("动画", "旋转")
        default_mat = self.app.meta.get("材质", "标准")
        default_color = self.app.meta.get("颜色", "#e94560")
        orbit = self.app.meta.get("轨道控制", "是")

        # 分类元素
        meshes = []
        lights = []
        camera_cfg = None
        texts = []
        scripts = []
        for el in self.app.elements:
            tag = el.tag.lower()
            if tag in ("light", "光源", "光"):
                lights.append(el)
            elif tag in ("camera", "相机"):
                camera_cfg = self._attrs_dict(el)
            elif tag in ("h1", "h2", "h3", "p", "label", "text", "文字"):
                texts.append(el)
            elif tag == "脚本":
                scripts.append(el.text)
            else:
                meshes.append(el)

        # 生成对象 JS
        obj_js = self._build_meshes_js(meshes, default_mat, default_color)
        light_js = self._build_lights_js(lights)
        cam_js = self._build_camera_js(camera_cfg)
        anim_js = self._build_anim_js(animation, meshes)

        # UI 文字
        text_html = ""
        for t in texts:
            tag = t.tag.lower()
            if tag in ("h1", "h2", "h3"):
                text_html += f'<{tag}>{self._escape_html(t.text)}</{tag}>\n'
            else:
                text_html += f'<p>{self._escape_html(t.text)}</p>\n'

        # OrbitControls
        orbit_js = ""
        if orbit == "是":
            orbit_js = (
                "// 轨道控制\n"
                "const controls = new OrbitControls(camera, renderer.domElement);\n"
                "controls.enableDamping = true;\n"
                "controls.dampingFactor = 0.05;\n"
            )

        custom_js = "\n".join(scripts)

        return (
            f"<!DOCTYPE html>\n"
            f'<html lang="zh-CN">\n'
            f"<head>\n"
            f'  <meta charset="UTF-8">\n'
            f"  <title>{self._escape_html(title)}</title>\n"
            f"  <style>\n"
            f"    * {{ margin: 0; padding: 0; }}\n"
            f"    body {{ background: {bg}; overflow: hidden; "
            f'font-family: "Microsoft YaHei", sans-serif; }}\n'
            f"    h1, p {{ color: #eee; padding: 10px 20px; "
            f"position: absolute; z-index: 10; }}\n"
            f"    h1 {{ top: 0; }} p {{ top: 50px; color: #aaa; }}\n"
            f"    canvas {{ display: block; }}\n"
            f"  </style>\n"
            f"</head>\n"
            f"<body>\n"
            f"  {text_html}"
            f'  <script type="importmap">\n'
            f'  {{\n'
            f'    "imports": {{\n'
            f'      "three": '
            f'"https://unpkg.com/three@0.160.0/build/three.module.js",\n'
            f'      "three/addons/": '
            f'"https://unpkg.com/three@0.160.0/examples/jsm/"\n'
            f"    }}\n"
            f"  }}\n"
            f"  </script>\n"
            f'  <script type="module">\n'
            f"  import * as THREE from 'three';\n"
            f"  import {{ OrbitControls }} from 'three/addons/"
            f"controls/OrbitControls.js';\n\n"
            f"  // 场景\n"
            f"  const scene = new THREE.Scene();\n"
            f"  scene.background = new THREE.Color('{bg}');\n\n"
            f"  // 相机\n"
            f"{cam_js}\n\n"
            f"  // 渲染器\n"
            f"  const renderer = new THREE.WebGLRenderer({{antialias:true}});\n"
            f"  renderer.setSize(window.innerWidth, window.innerHeight);\n"
            f"  renderer.setPixelRatio(window.devicePixelRatio);\n"
            f"  renderer.shadowMap.enabled = true;\n"
            f"  document.body.appendChild(renderer.domElement);\n\n"
            f"  // 光源\n"
            f"{light_js}\n\n"
            f"  // 几何体\n"
            f"{obj_js}\n\n"
            f"  {orbit_js}\n"
            f"  // 动画循环\n"
            f"  function animate() {{\n"
            f"    requestAnimationFrame(animate);\n"
            f"{anim_js}\n"
            f"    {'controls.update();' if orbit == '是' else ''}\n"
            f"    renderer.render(scene, camera);\n"
            f"  }}\n"
            f"  animate();\n\n"
            f"  // 窗口缩放\n"
            f"  window.addEventListener('resize', () => {{\n"
            f"    camera.aspect = window.innerWidth/window.innerHeight;\n"
            f"    camera.updateProjectionMatrix();\n"
            f"    renderer.setSize(window.innerWidth, window.innerHeight);\n"
            f"  }});\n"
            f"{custom_js}\n"
            f"  </script>\n"
            f"</body>\n"
            f"</html>\n"
        )

    def _build_meshes_js(self, meshes: list, default_mat: str,
                         default_color: str) -> str:
        """生成几何体 JS 代码。"""
        lines = ["const objects = [];"]
        for i, el in enumerate(meshes):
            tag = el.tag.lower()
            a = self._attrs_dict(el)
            color = a.get("color", a.get("颜色", default_color))
            material = a.get("material", a.get("材质", default_mat))
            x = a.get("x", "0")
            y = a.get("y", "0")
            z = a.get("z", "0")
            rx = a.get("rx", "0")
            ry = a.get("ry", "0")
            rz = a.get("rz", "0")

            # 材质
            mat_js = self._material_js(material, color)

            # 几何体
            geo_js = self._geometry_js(tag, a)
            if geo_js is None:
                continue

            lines.append(f"  // 对象 {i}: {tag}")
            lines.append(f"  const geo{i} = {geo_js};")
            lines.append(f"  const mat{i} = {mat_js};")
            lines.append(f"  const mesh{i} = new THREE.Mesh(geo{i}, mat{i});")
            lines.append(f"  mesh{i}.position.set({x}, {y}, {z});")
            lines.append(f"  mesh{i}.rotation.set({rx}, {ry}, {rz});")
            lines.append(f"  mesh{i}.castShadow = true;")
            lines.append(f"  mesh{i}.receiveShadow = true;")
            lines.append(f"  scene.add(mesh{i});")
            lines.append(f"  objects.push(mesh{i});")
        return "\n".join(lines)

    def _geometry_js(self, tag: str, a: dict) -> str | None:
        """返回 Three.js 几何体构造代码。"""
        if tag in ("box", "cube", "立方体", "方块"):
            s = a.get("size", a.get("s", "1"))
            w = a.get("w", a.get("宽", s))
            h = a.get("h", a.get("高", s))
            d = a.get("d", a.get("深", s))
            return f"new THREE.BoxGeometry({w}, {h}, {d})"

        if tag in ("sphere", "ball", "球体", "球"):
            r = a.get("r", a.get("半径", "1"))
            return f"new THREE.SphereGeometry({r}, 32, 32)"

        if tag in ("cylinder", "圆柱", "柱体"):
            r = a.get("r", a.get("半径", "1"))
            h = a.get("h", a.get("高", "2"))
            return f"new THREE.CylinderGeometry({r}, {r}, {h}, 32)"

        if tag in ("cone", "圆锥", "锥体"):
            r = a.get("r", a.get("半径", "1"))
            h = a.get("h", a.get("高", "2"))
            return f"new THREE.ConeGeometry({r}, {h}, 32)"

        if tag in ("torus", "圆环", "环"):
            r = a.get("r", a.get("半径", "1"))
            tube = a.get("tube", a.get("管径", "0.3"))
            return f"new THREE.TorusGeometry({r}, {tube}, 16, 64)"

        if tag in ("plane", "平面", "板"):
            w = a.get("w", a.get("宽", "5"))
            h = a.get("h", a.get("高", "5"))
            return f"new THREE.PlaneGeometry({w}, {h})"

        if tag in ("gear", "齿轮"):
            r = a.get("r", a.get("半径", "1"))
            teeth = a.get("teeth", a.get("齿数", "12"))
            return (f"new THREE.CylinderGeometry({r}, {r}, 0.3, {teeth})")

        if tag in ("building", "建筑", "楼"):
            w = a.get("w", a.get("宽", "2"))
            h = a.get("h", a.get("高", "4"))
            d = a.get("d", a.get("深", "2"))
            return f"new THREE.BoxGeometry({w}, {h}, {d})"

        # 默认：立方体
        return "new THREE.BoxGeometry(1, 1, 1)"

    def _material_js(self, material: str, color: str) -> str:
        """返回材质构造代码。"""
        m = material.lower()
        if m in ("金属", "metal"):
            return (f'new THREE.MeshStandardMaterial({{'
                    f'color: "{color}", metalness: 0.8, roughness: 0.2}})')
        if m in ("玻璃", "glass"):
            return (f'new THREE.MeshPhysicalMaterial({{'
                    f'color: "{color}", transmission: 0.9, '
                    f'opacity: 0.7, transparent: true, roughness: 0.1}})')
        if m in ("线框", "wire", "wireframe"):
            return (f'new THREE.MeshBasicMaterial({{'
                    f'color: "{color}", wireframe: true}})')
        # 标准
        return (f'new THREE.MeshStandardMaterial({{'
                f'color: "{color}", metalness: 0.3, roughness: 0.7}})')

    def _build_lights_js(self, lights: list) -> str:
        """生成光源 JS。"""
        if not lights:
            return (
                "  // 默认光照\n"
                "  const ambLight = new THREE.AmbientLight(0xffffff, 0.4);\n"
                "  scene.add(ambLight);\n"
                "  const dirLight = new THREE.DirectionalLight(0xffffff, 1);\n"
                "  dirLight.position.set(5, 10, 5);\n"
                "  dirLight.castShadow = true;\n"
                "  scene.add(dirLight);"
            )
        lines = []
        for i, el in enumerate(lights):
            a = self._attrs_dict(el)
            ltype = a.get("type", a.get("类型", "方向"))
            color = a.get("color", a.get("颜色", "#ffffff"))
            intensity = a.get("intensity", a.get("强度", "1"))
            x = a.get("x", "5")
            y = a.get("y", "10")
            z = a.get("z", "5")
            t = ltype.lower()
            if t in ("环境", "ambient"):
                lines.append(
                    f"  const l{i} = new THREE.AmbientLight("
                    f"'{color}', {intensity});")
            elif t in ("点", "point"):
                lines.append(
                    f"  const l{i} = new THREE.PointLight("
                    f"'{color}', {intensity});")
                lines.append(f"  l{i}.position.set({x}, {y}, {z});")
            else:  # 方向光
                lines.append(
                    f"  const l{i} = new THREE.DirectionalLight("
                    f"'{color}', {intensity});")
                lines.append(f"  l{i}.position.set({x}, {y}, {z});")
                lines.append(f"  l{i}.castShadow = true;")
            lines.append(f"  scene.add(l{i});")
        return "\n".join(lines)

    def _build_camera_js(self, camera_cfg: dict | None) -> str:
        """生成相机 JS。"""
        if camera_cfg is None:
            return (
                "  const camera = new THREE.PerspectiveCamera("
                "60, window.innerWidth/window.innerHeight, 0.1, 1000);\n"
                "  camera.position.set(5, 5, 8);\n"
                "  camera.lookAt(0, 0, 0);"
            )
        x = camera_cfg.get("x", "5")
        y = camera_cfg.get("y", "5")
        z = camera_cfg.get("z", "8")
        fov = camera_cfg.get("fov", camera_cfg.get("视野", "60"))
        return (
            f"  const camera = new THREE.PerspectiveCamera("
            f"{fov}, window.innerWidth/window.innerHeight, 0.1, 1000);\n"
            f"  camera.position.set({x}, {y}, {z});\n"
            f"  camera.lookAt(0, 0, 0);"
        )

    def _build_anim_js(self, animation: str, meshes: list) -> str:
        """生成动画 JS。"""
        a = animation.lower()
        if a in ("旋转", "自转", "rotate", "spin"):
            return "    objects.forEach(o => { o.rotation.x += 0.01; o.rotation.y += 0.01; });"
        if a in ("弹跳", "bounce", "跳"):
            return ("    objects.forEach((o, i) => { "
                    "o.position.y = Math.sin(Date.now()*0.001 + i) * 0.5; });")
        if a in ("公转", "orbit"):
            return ("    objects.forEach((o, i) => { "
                    "let a = Date.now()*0.0005 + i*2; "
                    "o.position.x = Math.cos(a) * 3; "
                    "o.position.z = Math.sin(a) * 3; });")
        # 无动画
        return "    // 静态场景"

    def _attrs_dict(self, el: Element) -> dict[str, str]:
        return {k: v for k, v in el.attrs}

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
