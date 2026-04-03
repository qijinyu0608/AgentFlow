# AgentMesh 打包成 macOS 应用

## 可以，推荐先做成 `.app`

这个项目现在更适合打包成：

- `AgentMesh.app`
- 或者再额外压缩成 `AgentMesh-macOS.zip`

当前实现方式是：

- 前端 `Vue/Vite` 先构建
- 后端 `FastAPI` 托管前端静态资源
- 用 `PyInstaller` 先产出运行时目录
- 再组装成 macOS 的 `.app` 包

## 一键打包脚本

项目里已经补好脚本：

```bash
./scripts/build_macos_app.sh
```

它会自动完成：

1. 构建前端 `frontend/dist`
2. 安装 `PyInstaller`
3. 生成运行时目录 `dist/AgentMesh`
4. 组装成 `dist-macos/AgentMesh.app`
5. 再压缩成 `dist-macos/AgentMesh-macOS.zip`

## 产物位置

```txt
dist-macos/AgentMesh.app
dist-macos/AgentMesh-macOS.zip
```

## 运行效果

双击 `AgentMesh.app` 后，程序会：

- 启动本地服务
- 默认监听 `127.0.0.1:8001`
- 自动打开浏览器进入 AgentMesh WebUI

如果包内没有 `config.yaml`，程序会尝试根据 `config-template.yaml` 自动生成。

## 使用前准备

建议环境：

- macOS 12+
- Python 3.11
- Node.js 18+

如果你在仓库里已经有 `.venv`，脚本会优先使用：

```txt
.venv/bin/python
```

否则会退回到系统里的 `python3`。

## 直接执行

第一次可先给执行权限：

```bash
chmod +x scripts/build_macos_app.sh
./scripts/build_macos_app.sh
```

## 需要注意

### 1. 这是 `.app`，不是 `.dmg`

现在已经能做成 mac 的应用包形式 `.app`。  
如果你后面还想做成可分发安装镜像 `.dmg`，我也可以继续帮你补。

### 2. 首次打开可能被 Gatekeeper 拦一下

如果是本地自行打包的 app，macOS 可能会提示来源未验证。  
这种情况下通常右键应用，选择“打开”一次即可。

### 3. 目前更偏“本地桌面壳”

它本质上还是：

- 本地 Python 服务
- 浏览器打开 WebUI

优点是改造成本低、维护简单。  
如果你后面想要更像原生桌面应用，我可以再帮你往 `pywebview`、`Tauri` 或 Electron 方向收。 
