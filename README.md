# CodexPetLimitRings · 原生桌宠双法力环

给 **Codex Desktop 自带的 Mini / Pet** 增加一个**同心双环徽章**：紫色外环是 **5 小时**，蓝色内环是**每周**剩余额度；中间显示 `41/91` 这样的整数，不加百分号。不替换宠物、不修改 Codex 文件、不要求 API Key。

- 优先读取 Codex 自身保存的宠物位置和 `mascot` 区域，由真实可见的 Windows 宿主窗口验证；不再直接拿 888×1080 透明宿主边缘猜龙娘位置。检测到角色位置变化或鼠标拖动角色时隐藏，稳定约 0.55–0.6 秒后显示。
- 拖动**整个同心双环**调整相对角色位置，自动保存偏移；因定位参考从宿主切换为角色，旧版 V1/V2 偏移自动失效但不会删除旧文件。
- 使用 Codex **App Server** 的只读 `account/rateLimits/read`，**不读取 `auth.json` 或复制令牌**。
- 默认每 60 秒刷新；右键查看重置时间、立即刷新、重置位置、退出。
- 适配 Windows 10/11 的透明窗口、多显示器和 DPI。
- **外观配置完全外置**：两个圆环的直径、粗细、颜色、磨砂底盘、柔和投影、背景、字体和跟随位置；修改 `config.json` 后约 1 秒自动重新加载。
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

## 一键启动与开机自启管理

现在无需记 PowerShell 参数，项目根目录提供以下入口（直接双击即可）：

| 文件 | 用途 |
|---|---|
| `start.cmd` | **退出圆环后重新启动**；优先使用 `pythonw.exe`，不会留下控制台 |
| `autostart-on.cmd` | **创建 / 更新当前用户的开机自启快捷方式** |
| `autostart-off.cmd` | **停用开机自启**（只删除本项目的当前用户启动快捷方式） |
| `autostart-status.cmd` | 检查自启是否安装以及对应的 Python / 脚本路径 |

**在圆环上右键**，另外新增「重新启动圆环」「启用开机自启」「停用开机自启」「查看自启状态」，不必再打开项目目录。重启会等待旧进程正常结束、单实例锁释放后才启动新实例，不会终止其他 Python / Codex 进程。

注意两个不同的动作：
- **退出圆环**：停止本次运行；已设置的开机自启仍保留。此时双击 `start.cmd` 即可重新显示。原生小龙娘不用重启。
- **停用开机自启**：阻止下次 Windows 登录时自动启动；**已经运行的圆环不会被关闭**。如果想两者都停用，再右键退出圆环即可。

启用自启**不会立即启动圆环**；要在本次 Windows 登录会话中启动，请双击 `start.cmd`。若只是把原生 Codex Mini 隐藏，圆环会随之隐藏、监听进程仍在，再次显示 Mini 时自动出现。

高级操作依旧可以使用 `scripts/Autostart.ps1 -Mode Install|Remove|Status`。所有启动项修改只作用于**当前用户的 Startup 文件夹**，无管理员权限要求。

## 操作

- **移动位置**：按住同心圆环拖动，松手保存相对宠物的偏移。
- **查看详情**：鼠标悬停查看 5h、7d 的准确百分比、重置时间与数据新鲜度。
- **右键菜单**：立即刷新、恢复默认位置、**重新启动圆环、启用/停用/查看开机自启**、退出。
- **退出**：右键 → 退出（不会关闭 Codex；仅隐藏 Mini 只会隐藏圆环，不会结束后台观察进程）。
- **重新打开**：直接双击 `start.cmd`，或运行 `python main.py`。用户登录自启是可选项，默认不自动注册。

个人位置/校准文件：`%LOCALAPPDATA%\CodexPetLimitRings\settings.json`。
可编辑的外观配置：项目根目录 `config.json`（见下）。

圆环不会代替 Codex 对额度的真实判断。仅当 App Server 返回了**准确的 300 / 10080 分钟窗口**时，才分别标为 5h / 7d；缺失数据将显示 `--`。

## V7.3：抖动点阵重写阴影与假毛玻璃

V7.1 的「三道淡紫轮廓 + 实色瓷盘」在多数壁纸上几乎看不出来，也没有阴影该有的重量感。V7.3 换了一条完全不同的路线：**有序抖动（Ordered Dithering）**。

透明色键窗口里每个像素要么完全透明、要么完全不透明（这正是当年半透明 PNG 变黑胎的原因）。V7.3 把每一层装饰（阴影、磨砂底盘、亮边、高光）换算成 **4×4 Bayer 点阵**：不透明颜色点与透明小孔按透明度比例混合，眼睛会把点阵与从小孔透出的真实桌面平均掉，于是：

- 阴影是真正**随背景变化的柔影**：靠近徽章处密、向外指数渐隐，带 `shadowOffsetX/Y` 偏移（光源在左上时阴影向右下沉）。
- 底盘是**能看到壁纸的磨砂玻璃**：`fillOpacity` 现在是真实透光率，顶部略亮、底部略透，边缘有亮色 rim 和左上高光，右下有淡暗反光，星微球面感。
- 所有像素仍是不透明实色点（Tk Canvas 矩形），**依旧不碰 PNG Alpha**、不截图、不依赖 Pillow，Windows Tk 兼容性与 V7.1 一致。

点阵在 96 DPI 下已经很细，在 150%/200% 缩放屏上更接近连续渐变。徽章跟随宠物移动时本来就隐藏，不会有点阵抖动残影。玻璃点阵只在配置/DPI 变化时重建，每分钟额度刷新只重画圆环和文字，性能无变化。

调优建议（写进 `config.json` 的 `glass` 段即可，约 1 秒热生效）：

```json
{
  "glass": {
    "enabled": true,
    "fillColor": "#f7f2ff",
    "fillOpacity": 62,
    "shadowColor": "#2d244d",
    "shadowOpacity": 30,
    "shadowBlur": 10,
    "shadowSpread": 1,
    "shadowOffsetX": 0,
    "shadowOffsetY": 3,
    "rimColor": "#ffffff",
    "rimOpacity": 70,
    "highlightColor": "#ffffff",
    "highlightOpacity": 55,
    "outerMargin": 1
  }
}
```

- `fillOpacity` 越低越透壁纸（20–40 抽丝磨砂，80+ 接近瓷盘）；深色壁纸建议降低，浅色壁纸可以拉高。
- `shadowOpacity` 是阴影峰值强度；深色壁纸可以适当加大，否则阴影不明显。
- `shadowBlur` 是渐隐宽度（物理像素）；极端大阴影会自动限制，避免窗口膨胀。
- 想要无装饰双环：`glass.enabled = false`。

离线预览：`python scripts/glass_preview.py` 会用同一套抖动规划器在浅色/深色/照片/棋盘四种模拟壁纸上渲染徽章并导出 `logs/glass_preview.png`，不启动 Tk。

## V7.2：默认恢复极简双环

Windows 实机验收表明，浅色轮廓依然容易让小圆环看起来像一个繁复的线圈。**现在默认完全关闭所有假毛玻璃、阴影、光晕和瓷底**，只保留原有紫蓝两个同心进度环与中间的额度数字。UIA 跟随、淡入淡出、自启动作保持不变。

- 新克隆或从未创建个人主题 `config.json` 的用户，拉取后就默认关闭玻璃装饰。
- 已有本地 `config.json` 的用户需要手动改成 `"glass": {"enabled": false}`；个人主题始终优先于默认值，升级不会替你覆盖它。
- 旧装饰实现仍作为实验性选项保留，但不推荐在 Windows Tk 的透明色键模式中开启。

## V7.1：修复黑色轮胎阴影（Windows Tk 透明合成兼容）

用户的 Windows 实测发现 V7 的 RGBA 半透明 PNG 在 Tk `-transparentcolor` 分层窗口上出现**整圈不透明黑色底**。这是 Windows/Tk 合成路径兼容问题，不是期望中的阴影。

**V7.1 已彻底停止在 Tk 上绘制半透明 PNG**，改为仅使用安全的 Canvas 实色图元，保留窗口其他区域原来的透明色键。视觉改为：

- 外圈只有三道极浅的淡紫色柔和轮廓，不再有厚重的黑色阴影。
- 底盘缩到**每周内环内部**，浅紫白色，周围保留大部分壁纸可见。
- 细白边与微弱高光营造「瓷感 / 假毛玻璃」视觉，不是真桌面模糊。
- 完全不使用桌面截图、Pillow、Win32 Acrylic / BlurBehind 或 PNG 局部 Alpha。

仍然沿用 `config.json` 的 `glass` 设置：

```json
{
  "glass": {
    "enabled": true,
    "fillColor": "#f7f2ff",
    "fillOpacity": 56,
    "shadowColor": "#2d244d",
    "shadowOpacity": 24,
    "shadowBlur": 8,
    "shadowSpread": 1,
    "shadowOffsetX": 1,
    "shadowOffsetY": 3,
    "rimColor": "#ffffff",
    "rimOpacity": 74,
    "highlightColor": "#ffffff",
    "highlightOpacity": 35,
    "outerMargin": 2
  }
}
```

**重要限制**：Canvas 不支持对单个椭圆设置真正的 Alpha 透明度；上述透明度参数现在只调整颜色的明暗/柔和程度，而**不是透过圆盘看到壁纸的真实透光率**。阴影扩散、偏移已限制在少量像素内，避免形成另一圈巨大底盘。设置 `glass.enabled=false` 可立即恢复无底盘的双环。

保存配置会热更新，但如果之前的窗口还保持旧的 PNG 图层，请退出旧进程后重新运行 `python main.py`。已安装的 Windows 登录自启快捷方式无需修改。真实 Tk 视觉合成仍以你本机截图为准。

## V6：宠物生命周期联动、淡入淡出、可选登录自启

新的默认行为：**只在原生 Mini 宠物的 UIA Image 元素可见时显示圆环**。宿主透明 HWND 即使继续存在，`not_found`、`pending` 或过期的 UIA 坐标都不会让圆环在旧位置冒出来。关掉 / 隐藏 Mini 后圆环淡出、完全隐藏；重新显示 Mini 后自动恢复。**圆环的 Python 监听进程仍在后台运行**，这是自动恢复所必需的。右键「退出圆环」会真正结束进程，重开需要再次启动。

UI 动画采用非阻塞的渐隐渐现（默认淡入 220ms、淡出 130ms），不再每次都立即 `withdraw()`。持续移动时仍暂时隐藏，以免低频 UIA 数据导致法力环追着角色跳动。请自行在 Windows 上验收 Tk 的 `-alpha` 与透明色同时使用的表现；如果本机不兼容，可以在配置中关闭动画。

```json
{
  "animation": {
    "enabled": true,
    "fadeInMs": 220,
    "fadeOutMs": 130,
    "frameMs": 33
  },
  "visibility": {
    "requireUIA": true
  }
}
```

这些设置已经在 `config.example.json` 提供，复制为 `config.json` 后保存即可热加载。只有旧版 Codex 的 UIA 无法工作时才建议将 `requireUIA` 改为 `false`；这会重新允许宿主/手动估算，宠物隐藏时可能残留圆环。

**让它跟随宠物自动出现，无须手工启动程序**，需要一个很小的后台观察进程。可以选择在 Windows 用户登录时启动它（不会改 Codex 安装内容、不会请求管理员权限），等宠物出现才显示：

```powershell
# 当前用户登录自启（可选，一次安装即可）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Autostart.ps1 -Mode Install

# 检查安装状态
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Autostart.ps1 -Mode Status

# 不想开机自启时，随时卸载启动项
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Autostart.ps1 -Mode Remove
```

登录启动的是当前 Python 环境的 `pythonw.exe main.py`，它不产生控制台窗口；即使 Codex 没启动，观察进程仍会静默等待（没有 Mini HWND 时不启动 UIA 子进程）。不会自动修改或关闭 Codex。只注销 / 重启 Windows 才会重新执行开机启动项；在本次登录会话内测试，仍可先 `python main.py`。

若要**后台进程也在宠物关闭时完全退出**，则必须再设一个独立守护进程来检测下一次 Mini 出现。当前采用单常驻观察进程，避免为一个小圆环再增加两层进程管理。

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
| `background.enabled` | 是否绘制传统纯色圆形背景；开启玻璃时不使用 |
| `background.color / borderColor / borderWidth / padding` | 传统背景颜色、描边和留白 |
| `glass.enabled / fillColor / fillOpacity` | 磨砂玻璃开关、底盘色和真实透光率（抖动点阵） |
| `glass.shadowColor / shadowOpacity / shadowBlur` | 柔影颜色、峰值强度和渐隐宽度；`shadowOffsetX/Y` 控制光源方向 |
| `glass.rimColor / rimOpacity / highlightOpacity` | 亮色描边、左上高光与右下淡暗反光 |
| `text.fontFamily / fontSize / bold / color` | 中心数字字体、大小、粗细和颜色 |
| `text.separator / showPercentSign` | `41/91` 分隔符和百分号显示 |
| `position.side / gap / verticalRatio` | 优先贴角色左侧或右侧、距离和纵向对齐位置 |
| `position.offsetX / offsetY / settleMs` | 额外偏移和移动后恢复显示的等待时间 |

注意：Tk 透明色键窗口中每个像素只能全透明或不透明。假毛玻璃与柔影通过 **4×4 有序抖动点阵**模拟：不透明色点与透明小孔按比例混合，眼睛把它们与透出的真实桌面平均，得到随背景变化的半透明观感（并非真正模糊壁纸）。颜色请输入 `#RRGGBB`。非常极端的环大小会被配置校验限制为合理范围。

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
- `rings/glass.py`：抖动点阵规划器——把柔影、磨砂底盘、亮边、高光换算成不透明 1px 矩形，完全不依赖 PNG Alpha。
- `rings/config.py`：外观配置验证与自动重新加载。
- `rings/calibration.py`：每屏手动校准与本地位置保存。
- `main.py`：启动、预览、诊断入口。

## 设计参考

参考 [Codexy-pet-usages-ring](https://github.com/himomohi/Codexy-pet-usages-ring) 的原生宠物跟随与透明圆环交互思路，以及 [codex-usage-overlay](https://github.com/jiaotashidi-bi/codex-usage-overlay) 的 App Server 查询思路。**本仓库为独立、精简实现，不直接复制上游项目的大段源码或素材**。

不访问非公开的 `wham/usage` 接口；不保存登录凭证、提示词、仓库内容或会话文本。

## 已知限制

- 只能在 Windows 桌面运行；没有原生宠物时默认隐藏（`--demo` 除外）。
- GitHub CI 校验 Python 编译、额度解析、主题配置、渐变过渡、手动校准和移动检测；**真实 Windows 桌面位置、DPI、拖动及动画显隐仍需要 ANMI-SERVER 实机验收**。
- Codex 或 Windows 以后修改窗口类型、UI 状态字段时，可能需要调整识别条件。**真实桌面跟随仍待你的主副屏实测**；若无法找到有效宿主窗口，程序宁可隐藏并让 `--diagnose` 报告原因，不假装已经跟随。
