# matha_mobile

> **定位标注（2026-10，P2 降级）：** 本目录是仓库内的**实验性 Flutter 前端**，
> 不在 `make check` 门禁覆盖面内，不代表主线 v4.6.0 现状。
> 历史上 `assets/pyodide/build_wasm.{bat,sh}` 与 `assets/deploy.{bat,sh}` 曾硬编码
> 旧版本号 4.4.16 漂移于主线，现已改为构建时从唯一版本源
> [`src/__version__.py`](../src/__version__.py) 读取，不再各说各话（读不到即报错退出，
> 拒绝以硬编版本继续）。
> 口径见 [`docs/KNOWN_ISSUES.md`](../docs/KNOWN_ISSUES.md) 第七节 7b。

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
