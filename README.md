# AgentFlow

AgentFlow 是一个面向多智能体协作执行的项目，重点解决“一个任务如何在多个角色之间被拆解、推进、调用工具、补充记忆并最终收束结果”的问题。

它不是单纯的聊天壳子，而是一套配置驱动的 Agent 协作系统。你可以在配置里定义团队、角色、模型、工具和技能，让系统按既定流程完成研究、开发、测试、知识检索等任务。

## 项目定位

这个项目当前更适合以下场景：

- 搭建本地可运行的多智能体协作原型
- 通过 Web 界面观察任务分发、工具调用和协作轨迹
- 为复杂任务提供角色分工、上下文补强和过程回放能力
- 在已有业务中集成记忆、向量检索和文档入库能力

从运行机制上看，AgentFlow 的核心链路是：

`用户任务 -> 团队装配 -> 上下文补强 -> 角色执行 -> 工具调用 -> Agent 交接 -> 最终输出 -> 事件落库与回放`

如果你想深入理解系统内部是如何工作的，可以直接阅读：

- [项目运行机制梳理（中文）](./docs/project-runtime-mechanism-cn.md)
- [运行冒烟检查清单](./docs/runtime-smoke-checklist.md)
- [工具能力说明](./docs/tools.md)

## 当前能力

### 1. 多智能体协作

- 支持通过 `config.yaml` 定义团队、角色、规则、最大步数和最终输出角色
- 支持基于任务内容选择初始 Agent，并在多个角色之间进行交接
- 支持把执行过程中的协作事件完整记录下来，便于回放和排障

### 2. 模型与工具统一接入

- 支持 OpenAI、Claude、DeepSeek 及 OpenAI 兼容接口
- 内置搜索、浏览器、读写文件、编辑、终端、时间、计算等工具
- 支持 Skill 机制，把提示词和工具组合复用到不同角色上

### 3. 记忆与 RAG

- 支持长期记忆、会话消息、摘要信息和向量检索
- 支持文档上传、标注、切块和向量入库
- 支持执行前做上下文补强，让 Agent 带着已有知识开始工作

### 4. Web 工作台

- 后端提供 FastAPI 接口和 WebSocket 实时任务流
- 前端提供任务工作区、过程面板、调度面板、工具结果和协作详情页
- 可以看到任务从发起到结束的完整过程，而不是只看最终回答

## 项目结构

```text
.
├── agentmesh/                 # 核心后端代码
│   ├── api/                   # FastAPI 路由
│   ├── protocol/              # Agent / Team / Task 等核心协议
│   ├── service/               # 执行、记忆、上下文、事件服务
│   ├── tools/                 # 内置工具
│   ├── skills/                # 内置技能
│   └── models/                # 模型适配层
├── frontend/                  # Vue 3 前端工作台
├── docs/                      # 中文说明、运行机制和打包文档
├── scripts/                   # 运维、迁移和检查脚本
├── config-template.yaml       # 配置模板
└── main.py                    # CLI / API 启动入口
```

说明：

- 仓库名称已使用 `AgentFlow`
- 当前 Python 包名和部分代码命名仍然保留为 `agentmesh`，这不影响运行

## 快速开始

### 1. 安装依赖

建议使用 Python 3.11+：

```bash
pip install -r requirements.txt
```

如果你需要浏览器能力：

```bash
pip install browser-use==0.1.40
playwright install
```

### 2. 初始化配置

```bash
cp config-template.yaml config.yaml
```

然后在 `config.yaml` 中填写你自己的模型配置、API Key、团队定义和数据库路径。

默认情况下：

- 会话与任务数据存放在 `data/sqlite/conversation.db`
- 记忆与文档数据存放在 `data/sqlite/memory.db`
- 向量数据存放在 `data/sqlite/vector.db`

### 3. 命令行运行

查看可用团队：

```bash
python3 main.py -l
```

执行单次任务：

```bash
python3 main.py -t general_team -q "帮我分析多智能体系统的应用场景"
```

进入交互模式：

```bash
python3 main.py -t software_team
```

### 4. 启动后端服务

```bash
python3 main.py -s -p 8001
```

启动后可访问：

- API 文档：`http://localhost:8001/docs`
- 健康检查：`http://localhost:8001/api/v1/health`

### 5. 启动前端页面

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

`http://localhost:3000`

如需连接自定义后端地址：

```bash
cd frontend
VITE_API_BASE=http://127.0.0.1:8001 npm run dev
```

## 配置说明

项目的运行方式主要由 `config.yaml` 驱动，重点包括：

- `models`：模型服务商、接口地址、密钥和模型名
- `tools`：工具级静态配置
- `embeddings`：向量化模型及检索配置
- `database`：SQLite 数据路径
- `skills.paths`：额外 skill 搜索路径
- `teams`：团队定义、角色职责、工具和技能

模板中内置了两个示例团队：

- `general_team`：适合研究、信息搜集、综合分析
- `software_team`：适合产品、开发、测试协同的软件任务

## 推荐阅读顺序

如果你是第一次接触这个项目，建议按下面顺序阅读：

1. [README](./README.md)
2. [项目运行机制梳理（中文）](./docs/project-runtime-mechanism-cn.md)
3. [运行冒烟检查清单](./docs/runtime-smoke-checklist.md)
4. [工具能力说明](./docs/tools.md)

如果你要做打包：

- [Windows EXE 打包说明](./docs/package-exe-cn.md)
- [macOS APP 打包说明](./docs/package-macos-cn.md)

## 当前适合继续优化的方向

- 把对外展示名称进一步统一为 `AgentFlow`
- 梳理前端首页和配置页的品牌文案
- 增加更贴合实际业务的默认团队模板
- 补充部署文档、接口示例和典型工作流案例

## License

本项目当前仓库使用 [MIT License](./LICENSE)。
