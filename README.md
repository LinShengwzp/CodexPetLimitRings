# CodexPetLimitRings · 原生桌宠双法力环

给 **Codex Desktop 自带的 Mini / Pet** 增加一个**同心双环徽章**：紫色外环是 **5 小时**，蓝色内环是**每周**剩余额度；中间显示 `41/91` 这样的整数，不加百分号。不替换宠物、不修改 Codex 文件、不要求 API Key。

- 优先读取 Codex 自身保存的宠物位置和 `mascot` 区域，由真实可见的 Windows 宿主窗口验证；不再直接拿 888×1080 透明宿主边缘猜龙娘位置。检测到角色位置变化或鼠标拖动角色时隐藏，稳定约 0.55–0.6 秒后显示。
- 拖动**整个同心双环**调整相对角色位置，自动保存偏移；因定位参考从宿主切换为角色，旧版 V1/V2 偏移自动失效但不会删除旧文件。
- 使用 Codex **App Server** 的只读 `account/rateLimits/read`，**不读取 `auth.json` 或复制令牌**。
- 默认每 60 秒刷新；右键查看重置时间、立即刷新、重置位置、退出。
- 适配 Windows 10/11 的透明窗口、多显示器和 DPI。
- 没拿到数据时显示 `--`，而不是编造 0% 或 100%。

> 当前仍是轻量实验版。目标是一个安静的小装饰，**不会额外显示第二只宠物**。这是独立非官方项目。

## 快速启动（Windows）

需要 Windows 10/11、Python **3.10+（含 Tkinter）**，以及已登录 ChatGPT 账户的 Codex 桌面端或 Codex CLI。**无第三方 Python 依赖**。

从仓库克隆 / 下载源码，在 PowerShell 中运行：

```powershell
git clone https://github.com/LinShengwzp/CodexPetLimitRings.git
cd CodexPetLimitRings

# 可选：在原生宠物旁预览同心双环（模拟 41/91，不查询额度）
python main.py --demo

# 只读检查额度接口，打印 5h / 7d 数据（不会运行图形界面）
python main.py --once

# 在 Codex 中打开 Mini / Pet 后启动
python main.py
```

也可以双击 `start.cmd`，它使用 `pythonw` 尝试无控制台启动。**第一次请先从终端运行**，便于排查。

已经有 Anaconda 的机器可直接使用 `C:\Users\<用户名>\anaconda3\python.exe`；如果没有安装 tkinter，需要补齐 Python 的 Tcl/Tk 组件。

## 操作

- **移动位置**：按住同心圆环拖动，松手保存相对宠物的偏移。
- **查看详情**：鼠标悬停查看 5h、7d 的准确百分比、重置时间与数据新鲜度。
- **右键菜单**：立即刷新 / 恢复默认位置 / 退出。
- **退出**：右键 → 退出（不会关闭 Codex）。
- **重新打开**：再次运行 `python main.py`；程序不自动注册 Windows 启动项。

设置文件：`%LOCALAPPDATA%\CodexPetLimitRings\settings.json`。

圆环不会代替 Codex 对额度的真实判断。仅当 App Server 返回了**准确的 300 / 10080 分钟窗口**时，才分别标为 5h / 7d；缺失数据将显示 `--`。

## V2 同心双环说明

- **外紫内蓝**，中心 `5h/7d` 的数值依次显示为 `41/91`，不是把两个独立圆圈并排。
- `python main.py --demo`：如果已检测到原生宠物，靠近宠物位置预览；否则在当前鼠标附近预览（可将鼠标放在副屏再运行）。模拟数据不会更改账户额度。
- 定位已改为解析 `%USERPROFILE%\.codex\.codex-global-state.json` 中的 `electron-avatar-overlay-bounds`，优先读取当前显示器对应的 `mascot` 细分几何信息。原生可见窗口用来验证当前状态，避免误认历史残留位置。此文件是 Codex UI 状态，不是登录凭据。若不含 `mascot` 数据，结果会明确标记为近似位置。
- 移动隐藏可识别 Codex 保存的位置变化，也会检测在龙娘区域内按住鼠标左键拖动；普通内部动画和未写入 UI 状态的程序化运动可能仍无法检测。
- V1/V2 的偏移不会自动迁移，因为参考位置已变化；第一次拖动或右键「恢复默认位置」会保存 V3 布局位置。

## 诊断与测试

```powershell
# 显示龙娘真实坐标、透明宿主坐标和定位来源
python main.py --probe

# 如果主屏仍无法检测，在主屏显示 Mini 后执行；只输出窗口几何和样式，不输出凭据或窗口标题
python main.py --diagnose

# 可用备用 Codex CLI 可执行文件覆盖默认自动探测
$env:CODEX_PET_CODEX_BIN = 'C:\Users\wzp12\AppData\Local\OpenAI\Codex\bin\<hash>\codex.exe'
python main.py --once

# 单元测试，不需要联网，不启动界面
python -m unittest discover -s tests -v
```

Codex 桌面安装 / 更新、宠物窗口属性变化可能影响探测，请先用 `--probe` 核实。额度接口查询限时并在后台线程执行，失败会保留已知值但标记为旧数据。

## 项目结构

- `rings/core.py`：限额解析、五小时和每周窗口校验、浮层位置计算。
- `rings/bridge.py`：Codex App Server 只读连接与超时处理。
- `rings/pet.py`：Windows 原生窗口验证、角色坐标选择、多显示器工作区。
- `rings/state.py`：只读解析 Codex 原生 Mini 的 UI 坐标和 mascot 信息。
- `rings/ui.py`：Tkinter 双圆环透明浮层、拖动、刷新、提示。
- `main.py`：启动、预览、诊断入口。

## 设计参考

参考 [Codexy-pet-usages-ring](https://github.com/himomohi/Codexy-pet-usages-ring) 的原生宠物跟随与透明圆环交互思路，以及 [codex-usage-overlay](https://github.com/jiaotashidi-bi/codex-usage-overlay) 的 App Server 查询思路。**本仓库为独立、精简实现，不直接复制上游项目的大段源码或素材**。

不访问非公开的 `wham/usage` 接口；不保存登录凭证、提示词、仓库内容或会话文本。

## 已知限制

- 只能在 Windows 桌面运行；没有原生宠物时默认隐藏（`--demo` 除外）。
- GitHub CI 校验 Python 编译、额度解析、跟随位置与移动检测；**真实 Windows 桌面位置、DPI、拖动及动画显隐仍需要 ANMI-SERVER 实机验收**。
- Codex 或 Windows 以后修改窗口类型、UI 状态字段时，可能需要调整识别条件。**真实桌面跟随仍待你的主副屏实测**；若无法找到有效宿主窗口，程序宁可隐藏并让 `--diagnose` 报告原因，不假装已经跟随。
