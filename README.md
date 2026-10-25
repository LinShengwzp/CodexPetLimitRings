# CodexPetLimitRings · 原生桌宠双法力环

给 **Codex Desktop 自带的 Mini / Pet** 增加一个**同心双环徽章**：紫色外环是 **5 小时**，蓝色内环是**每周**剩余额度；中间显示 `41/91` 这样的整数，不加百分号。不替换宠物、不修改 Codex 文件、不要求 API Key。

- 跟随原生宠物宿主窗口定位；检测到窗口移动时自动隐藏，停止移动约 0.55 秒后显示；宠物隐藏时圆环也隐藏。
- 拖动**整个同心双环**调整相对位置，自动保存偏移；首次升级 V1→V2 时旧版偏移不再使用。
- 使用 Codex **App Server** 的只读 `account/rateLimits/read`，**不读取 `auth.json` 或复制令牌**。
- 默认每 60 秒刷新；右键查看重置时间、立即刷新、重置位置、退出。
- 适配 Windows 10/11 的透明窗口、多显示器和 DPI。
- 没拿到数据时显示 `--`，而不是编造 0% 或 100%。

> 当前版本为轻量 V1。目标是一个安静的小装饰，**不会额外显示第二只宠物**。这是独立非官方项目。

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
- 新定位处理了部分 Codex 版本返回 **888×1080 这样的大型透明宿主窗口**的问题；无法直接读取人物素材的真实屏幕边界，初次位置仍可拖动微调。
- 移动隐藏的触发条件是 Windows 宿主窗口位置变化。窗口内部角色动画不属于 Win32 位移检测范围。
- V1 的偏移设置不会自动迁移，因为参考位置已变化；第一次拖动或右键「恢复默认位置」会保存新的布局版本。

## 诊断与测试

```powershell
# 显示是否找到真实的 Codex Pet 窗口（建议先打开 Mini）
python main.py --probe

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
- `rings/pet.py`：Windows 原生 Pet 窗口探测和多显示器工作区。
- `rings/ui.py`：Tkinter 双圆环透明浮层、拖动、刷新、提示。
- `main.py`：启动、预览、诊断入口。

## 设计参考

参考 [Codexy-pet-usages-ring](https://github.com/himomohi/Codexy-pet-usages-ring) 的原生宠物跟随与透明圆环交互思路，以及 [codex-usage-overlay](https://github.com/jiaotashidi-bi/codex-usage-overlay) 的 App Server 查询思路。**本仓库为独立、精简实现，不直接复制上游项目的大段源码或素材**。

不访问非公开的 `wham/usage` 接口；不保存登录凭证、提示词、仓库内容或会话文本。

## 已知限制

- 只能在 Windows 桌面运行；没有原生宠物时默认隐藏（`--demo` 除外）。
- GitHub CI 校验 Python 编译、额度解析、跟随位置与移动检测；**真实 Windows 桌面位置、DPI、拖动及动画显隐仍需要 ANMI-SERVER 实机验收**。
- Codex 或 Windows 以后修改窗口类型时，可能需要调整识别条件。**仅能通过 Win32 宿主窗口边界感知移动**：若宠物是在固定宿主窗口内部用 CSS / 精灵图移动，窗口边界不变时不能自动识别该动作，也就不会触发隐藏。
