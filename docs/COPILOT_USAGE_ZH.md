# 在 GitHub Copilot 中使用 Argus

本文介绍如何把 Argus 注册为 GitHub Copilot 可调用的 MCP Server，并在 Copilot Chat 或 Copilot CLI 中完成一次基于日志证据的故障诊断。

## 工作方式

Argus 是一个只读的日志检索 MCP Server。GitHub Copilot 负责理解问题、选择工具和总结诊断结论；Argus 只负责从管理员批准的日志源中返回证据。

典型流程：

1. 用户向 Copilot 描述故障。
2. Copilot 调用 `list_log_sources` 查看允许访问的日志源。
3. Copilot 调用 `search_logs` 搜索错误、超时或异常。
4. Copilot 使用返回的 cursor 调用 `get_log_context` 获取前后文。
5. Copilot 根据日志证据给出初步原因、影响范围和后续排查建议。

## 前置条件

- Python 3.11 或更高版本
- Git
- 已安装并可正常运行的 Argus
- 已启用 GitHub Copilot Chat Agent 模式，或已安装 GitHub Copilot CLI

检查基础环境：

```bash
python3 --version
git --version
```

如果使用 VS Code 中的 Copilot Chat，请确认 GitHub Copilot 扩展已登录，并能切换到 Agent 模式。

如果使用 Copilot CLI，请确认命令可用：

```bash
copilot --version
```

## 1. 下载并安装 Argus

```bash
git clone https://github.com/xiaoyi001yeye/Argus.git
cd Argus

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

检查安装结果：

```bash
which argus
pytest
```

`which argus` 应返回当前项目虚拟环境中的绝对路径，例如：

```text
/Users/yourname/Argus/.venv/bin/argus
```

后续 MCP 配置建议使用这个绝对路径。

## 2. 配置允许访问的日志源

复制示例配置：

```bash
cp config/environments.example.yaml config/environments.yaml
```

编辑 `config/environments.yaml`：

```yaml
environments:
  local:
    provider: local
    log_sources:
      order-service:
        path: /Users/yourname/logs/order-service.log
        description: 订单服务应用日志

      user-service:
        path: /Users/yourname/logs/user-service.log
        description: 用户服务应用日志
```

配置说明：

- `local` 是环境名称。
- `order-service` 和 `user-service` 是暴露给 Copilot 的逻辑日志源 ID。
- `path` 是 Argus 实际读取的日志文件。
- Copilot 不能自行传入文件路径，只能访问配置白名单中的日志源。

首次测试也可以保留项目自带的日志：

```yaml
environments:
  local:
    provider: local
    log_sources:
      order-service:
        path: fixtures/order-service.log
        description: Order service application log
```

配置文件不要提交真实生产路径、凭据或其他敏感信息。

## 3. 单独验证 Argus

在虚拟环境中运行：

```bash
argus
```

Argus 使用 STDIO MCP 传输。启动后没有 Web 页面，并会等待 MCP 客户端输入，这是正常现象。按 `Ctrl+C` 停止。

## 4. 注册到 VS Code Copilot Chat

VS Code 的 MCP 配置文件通常放在两个位置之一：

- 当前项目：`.vscode/mcp.json`
- 当前用户：通过命令面板运行 `MCP: Open User Configuration`

项目级配置适合只在当前仓库启用 Argus。创建或编辑 `.vscode/mcp.json`：

```json
{
  "servers": {
    "argus": {
      "type": "stdio",
      "command": "/Users/yourname/Argus/.venv/bin/argus",
      "cwd": "/Users/yourname/Argus",
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/Argus/config/environments.yaml"
      }
    }
  }
}
```

请把 `command`、`cwd` 和 `ARGUS_CONFIG` 替换为本机真实绝对路径。

保存后，在 `.vscode/mcp.json` 文件上方点击 `Start`，或从命令面板运行 `MCP: List Servers` 并启动 `argus`。VS Code 发现工具后，打开 Copilot Chat，切换到 `Agent` 模式，在工具列表中确认 `argus` 下有以下工具：

- `list_log_sources`
- `search_logs`
- `get_log_context`

## 5. 注册到 Copilot CLI

Copilot CLI 可以通过命令或配置文件添加 MCP Server。

### 使用命令添加

```bash
copilot mcp add argus \
  -e ARGUS_CONFIG=/Users/yourname/Argus/config/environments.yaml \
  -- /Users/yourname/Argus/.venv/bin/argus
```

### 使用用户级配置文件

编辑 `~/.copilot/mcp-config.json`：

```json
{
  "mcpServers": {
    "argus": {
      "type": "local",
      "command": "/Users/yourname/Argus/.venv/bin/argus",
      "args": [],
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/Argus/config/environments.yaml"
      },
      "tools": ["*"]
    }
  }
}
```

### 使用项目级配置文件

如果只希望当前仓库使用 Argus，可以在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "argus": {
      "type": "local",
      "command": "/Users/yourname/Argus/.venv/bin/argus",
      "args": [],
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/Argus/config/environments.yaml"
      },
      "tools": ["*"]
    }
  }
}
```

Copilot CLI 的项目级配置也可以放在 `.github/mcp.json`。如果要提交到仓库，确保配置里没有真实生产路径、密码、令牌或其他敏感信息。

注意：VS Code 使用 `.vscode/mcp.json` 和顶层 `servers`；Copilot CLI 使用 `mcpServers`。两者格式不同，不能直接混用。

## 6. 在 Copilot 中验证工具

在 VS Code Copilot Chat 的 Agent 模式，或 Copilot CLI 交互模式中输入：

```text
使用 Argus 查看 local 环境中有哪些日志源。
```

正常情况下，Copilot 会请求调用 `list_log_sources`，并返回配置中的日志源 ID 和描述。

如果 Copilot 要求确认工具调用，请确认工具名称和参数符合预期后再继续。

## 7. 完成一次故障诊断

可以直接给 Copilot 这样的提示词：

```text
使用 Argus 分析 local 环境中的 order-service 日志。

故障现象：
用户提交订单时返回失败。

分析要求：
1. 先列出可用日志源；
2. 搜索 error、failed、timeout、exception；
3. 对关键错误读取前后各 15 行；
4. 按时间顺序整理事件；
5. 区分日志已经证明的事实和推测；
6. 给出初步原因、证据、影响和下一步排查建议；
7. 如果日志不足以证明根因，要明确说明，不要编造结论。
```

Copilot 通常会依次执行以下调用：

```text
list_log_sources(environment="local")
```

如果 source 指向目录，可以先列出该 source 下的 `*.log` 文件：

```text
list_log_files(environment="local", source="order-service")
```

随后可用 `order-service/error.log` 作为 `source`，只搜索这个文件。

```text
search_logs(
  environment="local",
  source="order-service",
  query="error OR failed OR timeout OR exception",
  limit=100
)
```

```text
get_log_context(
  environment="local",
  source="order-service",
  cursor="order-service:37",
  before=15,
  after=15
)
```

也可以在提示词中限定 ISO-8601 时间范围：

```text
只分析 2026-07-29T09:00:00+08:00 到
2026-07-29T10:00:00+08:00 之间的 order-service 日志。
```

## 8. 推荐提示词模板

```text
你可以使用 Argus MCP 工具读取日志证据。

请遵守以下规则：
1. 先调用 list_log_sources，确认环境和日志源存在；
2. 只使用配置中暴露的 environment 和 source ID；
3. 不要要求 Argus 读取任意路径、执行 shell 命令或访问未配置主机；
4. 搜索时优先使用错误码、trace ID、订单号、用户 ID 或明确关键词；
5. 对关键命中调用 get_log_context 获取上下文；
6. 输出中把“日志证据”和“推测”分开；
7. 如果证据不足，明确说明还需要哪些日志或指标。
```

## 9. 常见问题

### Copilot 看不到 Argus 工具

检查配置文件路径和 JSON 格式：

- VS Code Copilot Chat：`.vscode/mcp.json` 使用顶层 `servers`。
- Copilot CLI：`~/.copilot/mcp-config.json`、`.mcp.json` 或 `.github/mcp.json` 使用 `mcpServers`。

确认 `command` 和 `ARGUS_CONFIG` 都是绝对路径，并重启 MCP Server 或重新打开 Copilot 会话。

### Argus 启动后没有输出

这是正常现象。Argus 使用 STDIO MCP 传输，会等待 MCP 客户端通过标准输入发送请求。

### 找不到配置文件

检查 `ARGUS_CONFIG`：

```bash
ls -l /Users/yourname/Argus/config/environments.yaml
```

如果没有设置 `ARGUS_CONFIG`，Argus 默认读取当前工作目录下的 `config/environments.yaml`。MCP 客户端启动进程时的工作目录可能不同，因此建议总是显式设置 `cwd` 和 `ARGUS_CONFIG`。

### 没有搜索结果

确认：

- `environment` 名称存在；
- `source` ID 和配置一致；
- 时间范围覆盖了实际日志时间；
- 查询词没有过窄；
- 日志文件路径存在，并且运行 Argus 的用户有读取权限。

### SSH 日志源连接失败

如果使用 `ssh_alias`，请确认别名已经配置免密登录。

如果使用 `ssh.host`、`ssh.username` 和 `ssh.password`，请确认密码正确，并且目标主机已经存在于系统 `known_hosts` 或配置的 `ssh.known_hosts` 中。

## 10. 安全边界

Argus 的安全边界是配置白名单，而不是 Copilot 的提示词。使用时应坚持：

- 不向 Copilot 暴露真实 SSH 密码、令牌或生产敏感路径；
- 不把真实生产配置提交到 Git；
- 只配置必要的日志源；
- 只给运行 Argus 的本地用户或远程 SSH 用户只读权限；
- 对 Copilot 的工具调用进行确认，尤其是首次连接新的 MCP Server 时。

更多环境配置和安全约束见 [环境管理说明](ENVIRONMENT_MANAGEMENT_ZH.md)。

## 参考

- [VS Code: Add and manage MCP servers](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
- [GitHub Docs: Extending Copilot Chat with MCP](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp)
- [GitHub Docs: Adding MCP servers for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)
