# AgentMesh 打包成 Windows EXE

## 当前方案

这个仓库现在采用的是：

- Python FastAPI 后端
- Vue/Vite 前端
- 前端构建后由后端直接托管
- 使用 PyInstaller 打包为 Windows `exe`

这样不需要再单独引入 Electron，维护成本更低。

## 先说明一个限制

如果你当前是在 macOS 上开发，**不能直接稳定产出 Windows `exe`**。  
PyInstaller 一般需要在目标平台上打包，也就是：

- 想要 `Windows exe`，最好在 Windows 机器上执行打包
- 或者放到 Windows 虚拟机 / Windows CI 里打包

## 推荐打包步骤

### 1. 准备 Windows 环境

建议：

- Windows 10/11
- Python 3.11
- Node.js 18+

### 2. 安装依赖

在项目根目录执行：

```bat
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 3. 一键打包

项目里已经补了脚本：

```bat
scripts\build_windows_exe.bat
```

它会自动做这几件事：

1. 构建前端 `frontend/dist`
2. 安装 `PyInstaller`
3. 按 `agentmesh.spec` 打包
4. 复制 `config.yaml`、`config-template.yaml`、`data` 到输出目录

## 输出结果

打包完成后，产物在：

```txt
dist\AgentMesh\
```

主程序：

```txt
dist\AgentMesh\AgentMesh.exe
```

## 运行方式

双击 `AgentMesh.exe` 后，程序会：

- 启动本地 FastAPI 服务
- 默认监听 `127.0.0.1:8001`
- 自动打开浏览器进入 WebUI

如果同目录下没有 `config.yaml`，程序会尝试用 `config-template.yaml` 自动生成一个。

## 常用说明

### 1. 为什么不是单文件 onefile？

这个项目更适合先做成 `onedir`：

- 前端静态资源更多
- 配置文件需要可编辑
- SQLite 数据和上传文件需要可读写
- 出问题时更容易排查

如果后面你一定要单文件，我也可以继续帮你再压成 `onefile`，但启动速度和读写路径处理会更复杂。

### 2. 打包后配置文件放哪？

放在 `AgentMesh.exe` 同级目录：

- `config.yaml`
- `data/`

### 3. 可以改端口吗？

可以，命令行启动：

```bat
AgentMesh.exe --server --port 9000 --open-browser
```

前端现在会优先走同源地址，不会再写死只连 `8001`。
