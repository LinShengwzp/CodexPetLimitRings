# CodexPetLimitRings · 原生桌宠双法力环

给 **Codex Desktop 自带的 Mini / Pet** 增加一个**同心双环徽章**：紫色外环是 **5 小时**，蓝色内环是**每周**剩余额度；中间显示 `41/91` 这样的整数，不加百分号。不替换宠物、不修改 Codex 文件、不要求 API Key。

- 优先读取 Codex 自身保存的宠物位置和 `mascot` 区域，由真实可见的 Windows 宿主窗口验证；不再直接拿 888×1080 透明宿主边缘猜龙娘位置。检测到角色位置变化或鼠标拖动角色时隐藏，稳定约 0.55–0.6 秒后显示。
- 拖动**整个同心双环**调整相对角色位置，自动保存偏移；因定位参考从宿主切换为角色，旧版 V1/V2 偏移自动失效但不会删除旧文件。
- 使用 Codex **App Server** 的只读 `account/rateLimits/read`，**不读取 `auth.json` 或复制令牌**。
- 默认每 60 秒刷新；右键查看重置时间、立即刷新、重置位置、退出。
- 适配 Windows 10/11 的透明窗口、多显示器和 DPI。
- **外观配置完全外置**：两个圆环的直径、粗细、颜色、底色、背景、字体和跟随位置；修改 `config.json` 后约 1 秒自动重新加载。
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

个人位置/校准文件：`%LOCALAPPDATA%\CodexPetLimitRings\settings.json`。
可编辑的外观配置：项目根目录 `config.json`（见下）。

圆环不会代替 Codex 对额度的真实判断。仅当 App Server 返回了**准确的 300 / 10080 分钟窗口**时，才分别标为 5h / 7d；缺失数据将显示 `--`。

## V5：原生 UI Automation 精确跟随（实验）

这版优先使用 **Windows UI Automation（UIA）**，从 Codex 原生 Mini 窗口的元素树直接读取宠物的 `ControlType.Image` 边界。来自真实机器的两条记录：

- 主屏：`[1594,429,1818,672]`（224×243 px）
- 副屏：`[3617,286,3841,529]`（224×243 px）

这些是人物 **UI 交互区域** 的坐标，不是 PNG 透明像素轮廓。外层透明宿主可以占满整个屏幕高度；现在不会把该宿主的 top/bottom 误认成人物边界。

- 开启宠物后直接 `python main.py --probe`，等待片刻查看 `position_source`。
- 理想结果是 `"position_source": "uia-image"`，同时 `precise_mascot_geometry: true`。
- 正常运行 `python main.py` 会启动一个隐藏的、只读 PowerShell UIA 子进程；约每 300ms 更新一次宠物坐标。图形界面不会等待 UIA 查询结果。
- 若一开始仍为 `approximate-host-corner`，把鼠标移到小龙娘身上再等一会儿。Chromium 有时需要鼠标 UIA 命中来激活无障碍元素。
- 自动搜索失败时，会退回 Codex UI 状态、旧手动校准或估算定位，不会更改系统设置或 Codex 文件。右键的**手动校准**仍可使用。
- 若要单独验证底层 UIA 子进程，可在 `--probe` 输出中取得 `hwnd`，运行：
  ```powershell
  powershell.exe -NoProfile -Sta -File .\scripts\PetUiaWatcher.ps1 -HostHwnd 134082
  ```
  这里的 `134082` 是示例，换成当次真实的 HWND。正常时每隔约 0.3 秒打印 `{"status":"ok","left":...}`，未找到时打印 `not_found`；Ctrl+C 退出。**不必把输出留在后台无人看管。**

特别注意：**代码语法和几何单元测试不等于 UIA 实机验收**。每台 Codex Desktop 的 Chromium 无障碍树可能不同。如果 `--probe` 没有显示 `uia-image`，先反馈该结果与子进程状态，再决定下一步调整。

## V4：校准真实角色位置与自定义外观

**为什么要校准？** 在某些 Codex Desktop 版本中，`--probe` 返回的只是覆盖整个屏幕高度的透明宿主窗口，且 `saved_codex_state.state_open_with_bounds=false`。此时操作系统无法告诉我们小龙娘在宿主的上半部分还是下半部分，程序应显示 `approximate-host-corner`，**绝不将估算冒充精确位置**。

校准方法：

1. 先右键圆环 → **校准小龙娘位置（5 秒内把鼠标移到她的中心）**。
2. 点击该菜单后，把鼠标移到小龙娘身体中心并停住，**不需要点击**，5 秒后自动记住位置。
3. 再拖动圆环微调相对间距。校准数据按显示器工作区分别保存。
4. 校准后可识别从小龙娘身上开始的鼠标拖拽，即使透明宿主窗口自身不动，也会记录鼠标位移并在停止后重新显示。角色自行播放动画、Codex 内部未写入状态的位移仍不保证能追踪。

如果暂时无法找到圆环，可先运行 `python main.py --demo` 预览；如果主屏 `--probe` 仍未找到宿主，请用 `python main.py --diagnose` 查看为什么没有匹配候选，避免盲目修改坐标。

**自定义外观**，在项目根目录运行：

```powershell
Copy-Item .\config.example.json .\config.json
notepad .\config.json
```

`config.json` 不受 Git 跟踪，后续 `git pull` 不会覆盖。保存后运行中的桌宠约 1 秒内自动生效，无需重启。

配置字段速查：

| 字段 | 功能 |
|---|---|
| `rings.outer.diameter / stroke / color` | 5 小时外环的直径（像素）、线宽和颜色 |
| `rings.inner.diameter / stroke / color` | 每周内环的直径、线宽和颜色 |
| `rings.trackColor` | 未使用进度部分的底色 |
| `rings.warningColor / criticalColor / unknownColor` | 低额度 / 极低额度 / 数据未知时使用的颜色 |
| `background.enabled` | 是否绘制圆形背景，默认为 `false`（透明） |
| `background.color / borderColor / borderWidth / padding` | 背景颜色、描边和留白 |
| `text.fontFamily / fontSize / bold / color` | 中心数字字体、大小、粗细和颜色 |
| `text.separator / showPercentSign` | `41/91` 分隔符和百分号显示 |
| `position.side / gap / verticalRatio` | 优先贴角色左侧或右侧、距离和纵向对齐位置 |
| `position.offsetX / offsetY / settleMs` | 额外偏移和移动后恢复显示的等待时间 |

注意：Tkinter 的普通画布背景只支持**全透明**或**不透明实色**，本版不支持单独设置背景半透明度。颜色请输入 `#RRGGBB`。非常极端的环大小会被配置校验限制为合理范围。

`--probe` 现在还会报告 `codex_state_file`（仅文件位置、是否存在和与宠物有关的字段名），不会打印 Codex 凭据。如果返回 `manual_calibration_active=true`，表示已采用人工校准的角色坐标。

## V2 同心双环说明

- **外紫内蓝**，中心 `5h/7d` 的数值依次显示为 `41/91`，不是把两个独立圆圈并排。
- `python main.py --demo`：如果已检测到原生宠物，靠近宠物位置预览；否则在当前鼠标附近预览（可将鼠标放在副屏再运行）。模拟数据不会更改账户额度。
- 定位已改为解析 `%USERPROFILE%\.codex\.codex-global-state.json` 中的 `electron-avatar-overlay-bounds`，优先读取当前显示器对应的 `mascot` 细分几何信息。原生可见窗口用来验证当前状态，避免误认历史残留位置。此文件是 Codex UI 状态，不是登录凭据。若不含 `mascot` 数据，结果会明确标记为近似位置。
- 移动隐藏可识别 Codex 保存的位置变化，也会检测在龙娘区域内按住鼠标左键拖动；普通内部动画和未写入 UI 状态的程序化运动可能仍无法检测。
- V1/V2/V3 的旧偏移不会自动迁移；校准并拖动后保存新的 V4 布局。

## 实时位置跟踪（排查移动不同步）

额度显示本身不受影响。排查坐标问题时，**请先退出正在运行的圆环**，然后运行：

```powershell
python main.py --trace-positions

# 更密集采样可选（默认 0.5 秒，最低 0.2 秒）
python main.py --trace-positions --trace-interval 0.3
```

程序运行时会在 **PowerShell 实时输出一行 JSON**，同时保存到项目的 `logs/positions-YYYYMMDD-HHMMSS.jsonl`（最大约 2MB，自动轮转）。不想查看日志时，仍使用普通的 `python main.py`。如果用 `start.cmd` / `pythonw` 启动，终端日志不可见，建议先用上面的命令调试。

主要字段：

| 字段 | 含义 |
|---|---|
| `host_rect` | Codex 原生透明宿主的 `[left,top,right,bottom]`，不等于小龙娘真实外形 |
| `raw_mascot_rect` | 当前探测器得到的角色矩形，可能只是估算 |
| `effective_mascot_rect` | **套用手动校准与鼠标拖动推断后**，用于计算圆环的角色矩形 |
| `position_source` | 定位来源，如 `approximate-host-corner` / `manually-calibrated` |
| `ring_target_rect` | 经过位置算法得到的圆环目标矩形 |
| `ring_window_observed` | Tk 当前观察到的实际窗口 `[x,y,width,height]`；隐藏时为 `null` |
| `visible` / `reason` | 是否显示及隐藏原因（例如 `pet_drag`、`host_or_mascot_settling`） |
| `mouse_xy` / `left_mouse_down` | 当前鼠标位置和左键状态 |
| `pet_drag_tracking` | 是否识别为正在拖动小龙娘 |
| `calibration_active` / `calibration_insets` | 本显示器校准是否生效及相对宿主的偏移 |
| `ring_drag_offset` / `config_offset` | 手动拖动和 JSON 配置带来的两套额外偏移 |

鼠标从小龙娘身上按住并移动时，观察 `mouse_xy`、`pet_drag_tracking`、`effective_mascot_rect` 是否一起改变。若 `mouse_xy` 已经变化，但 `pet_drag_tracking=false`，说明拖动入口的命中区域未匹配；若角色坐标已变化但 `ring_target_rect` 不变化，则继续检查位置算法。

可以在另一窗口查看最新日志：

```powershell
Get-Content (Get-ChildItem .\logs\positions-*.jsonl |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1).FullName -Tail 15 -Wait
```

**分享日志前请注意**：只记录窗口、坐标、鼠标位置和显隐状态，不采集登录凭据、提示词或窗口标题；但日志会显示你的屏幕布局及鼠标运动轨迹，不建议公开发布完整原始文件。

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
- `rings/pet.py`：Windows 原生窗口验证、UIA/状态/校准定位选择、多显示器工作区。
- `rings/uia.py`：非阻塞 PowerShell 子进程桥接与过期值处理。
- `scripts/PetUiaWatcher.ps1`：后台 UIA 元素查询，只输出人物的矩形坐标。
- `rings/state.py`：只读解析 Codex 原生 Mini 的 UI 坐标和 mascot 信息。
- `rings/ui.py`：Tkinter 双圆环透明浮层、拖动、刷新、提示和校准。
- `rings/config.py`：外观配置验证与自动重新加载。
- `rings/calibration.py`：每屏手动校准与本地位置保存。
- `main.py`：启动、预览、诊断入口。

## 设计参考

参考 [Codexy-pet-usages-ring](https://github.com/himomohi/Codexy-pet-usages-ring) 的原生宠物跟随与透明圆环交互思路，以及 [codex-usage-overlay](https://github.com/jiaotashidi-bi/codex-usage-overlay) 的 App Server 查询思路。**本仓库为独立、精简实现，不直接复制上游项目的大段源码或素材**。

不访问非公开的 `wham/usage` 接口；不保存登录凭证、提示词、仓库内容或会话文本。

## 已知限制

- 只能在 Windows 桌面运行；没有原生宠物时默认隐藏（`--demo` 除外）。
- GitHub CI 校验 Python 编译、额度解析、主题配置、手动校准和移动检测；**真实 Windows 桌面位置、DPI、拖动及动画显隐仍需要 ANMI-SERVER 实机验收**。
- Codex 或 Windows 以后修改窗口类型、UI 状态字段时，可能需要调整识别条件。**真实桌面跟随仍待你的主副屏实测**；若无法找到有效宿主窗口，程序宁可隐藏并让 `--diagnose` 报告原因，不假装已经跟随。
