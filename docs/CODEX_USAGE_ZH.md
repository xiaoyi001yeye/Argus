# 在 Codex 中使用 Argus

本文介绍如何在 macOS 或 Linux 上安装 Argus、配置日志源、将它注册为 Codex 的 MCP Server，并完成一次基于日志证据的故障诊断。

## 工作方式

Argus 是一个只读的日志检索 MCP Server。Codex 负责理解问题、调用工具和分析原因；Argus 负责从管理员批准的日志源中安全地返回证据。

典型流程：

1. 用户向 Codex 描述故障。
2. Codex 调用 `list_log_sources` 获取允许访问的日志源。
3. Codex 调用 `search_logs` 搜索错误、超时或异常。
4. Codex使用返回的 cursor 调用 `get_log_context` 获取前后文。
5. Codex 根据日志证据给出初步原因和后续排查建议。

## 前置条件

- Python 3.11 或更高版本
- Git
- 已安装并可正常运行的 Codex CLI

检查版本：

```bash
python3 --version
git --version
codex --version
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
- `order-service` 和 `user-service` 是暴露给 Codex 的逻辑日志源 ID。
- `path` 是 Argus 实际读取的日志文件。
- Codex 不能自行传入文件路径，只能访问配置白名单中的日志源。

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

## 4. 注册到 Codex

先取得项目路径和 Argus 命令的绝对路径：

```bash
pwd
which argus
```

然后注册 MCP Server。请把下面的路径替换为本机真实路径：

```bash
codex mcp add argus \
  --env ARGUS_CONFIG=/Users/yourname/Argus/config/environments.yaml \
  -- /Users/yourname/Argus/.venv/bin/argus
```

确认配置：

```bash
codex mcp list
```

如需删除后重新注册，可先查看帮助：

```bash
codex mcp --help
```

### 使用 config.toml 手动配置

也可以编辑全局的 `~/.codex/config.toml`：

```toml
[mcp_servers.argus]
command = "/Users/yourname/Argus/.venv/bin/argus"
cwd = "/Users/yourname/Argus"
startup_timeout_sec = 10
tool_timeout_sec = 60
enabled = true
required = false

[mcp_servers.argus.env]
ARGUS_CONFIG = "/Users/yourname/Argus/config/environments.yaml"
```

如果只希望当前项目使用 Argus，可以将相同配置放入项目的 `.codex/config.toml`。项目级 MCP 配置只会在可信项目中启用。

## 5. 在 Codex 中验证工具

启动 Codex：

```bash
codex
```

在 Codex TUI 中输入：

```text
/mcp
```

应能看到 `argus` 以及以下工具：

- `list_log_sources`
- `search_logs`
- `get_log_context`

修改 MCP 配置后，需要退出并重新启动 Codex。

第一次可以输入：

```text
使用 Argus 查看 local 环境中有哪些日志源。
```

## 6. 完成一次故障诊断

向 Codex 输入：

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

Codex 通常会依次执行以下调用。

### 列出日志源

```text
list_log_sources(environment="local")
```

### 搜索异常

```text
search_logs(
  environment="local",
  source="order-service",
  query="error OR failed OR timeout OR exception",
  limit=100
)
```

### 获取错误上下文

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
2026-07-29T10:00:00+08:00 之间的日志。
```

## 7. 当前限制

当前版本仍是 MVP：

- 完整支持本地日志文件。
- SSH Provider 已定义边界，但远程读取尚未启用。
- 不支持 `tail -f`。
- 不执行任意 Shell 命令。
- 不重启服务，也不修改服务器。
- 每次查询会重新读取日志文件。
- 本地 Provider 默认拒绝读取超过 10 MB 的文件。
- 查询支持普通文本以及由 `OR` 分隔的关键词，不支持正则表达式。
- 返回结果会对常见密码、Token、API Key 和 Authorization 内容进行脱敏。

## 8. 常见问题

### Codex 中看不到 Argus

依次检查：

```bash
codex mcp list
/Users/yourname/Argus/.venv/bin/argus
```

确认命令和配置文件都使用绝对路径，然后重启 Codex。

### 提示配置文件不存在

检查 `ARGUS_CONFIG`：

```bash
ls -l /Users/yourname/Argus/config/environments.yaml
```

### 提示日志源不存在

确认提示词中的环境名和 source ID 与 `config/environments.yaml` 完全一致。

### 提示日志文件不可用

检查配置中的日志路径是否存在，以及当前用户是否拥有读取权限。

### 修改代码后是否需要重新安装

本项目使用 `pip install -e` 以可编辑模式安装。一般修改 Python 源码后只需重启 Codex；依赖或入口配置发生变化时应重新执行安装命令。
