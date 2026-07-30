# 使用 Wheel 安装 Argus

本文说明如何在目标机器上使用 `argus_log_diagnostics-0.1.0-py3-none-any.whl`
安装 Argus，并注册给 Codex、GitHub Copilot 或其他支持 MCP 的 AI 终端使用。

## 1. 前置条件

- Python 3.11 或更高版本
- 可以访问 Python 包依赖源，例如 PyPI 或公司内部镜像
- 已拿到安装包：

```text
argus_log_diagnostics-0.1.0-py3-none-any.whl
```

检查 Python 版本：

```bash
python3 --version
```

## 2. 从 GitHub Actions 下载 Wheel

仓库的 GitHub Actions 会在 push、pull request 和手动触发时自动构建 Python 包。

下载步骤：

1. 打开 GitHub 仓库的 `Actions` 页面。
2. 选择 `Build Python Package` workflow。
3. 打开一次成功的运行记录。
4. 在页面底部的 `Artifacts` 区域下载 `argus-python-package`。
5. 解压 artifact，里面会包含 `.whl` 和源码包。

常用安装文件是：

```text
argus_log_diagnostics-0.1.0-py3-none-any.whl
```

## 3. 安装方式一：使用 pipx

推荐使用 `pipx` 安装命令行工具。它会为 Argus 创建独立环境，不污染系统 Python。

安装 pipx：

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

重新打开终端后安装 Argus：

```bash
pipx install ./argus_log_diagnostics-0.1.0-py3-none-any.whl
```

检查安装结果：

```bash
which argus
argus
```

`argus` 使用 STDIO MCP 传输。直接运行后没有 Web 页面，会等待 MCP 客户端输入，这是正常现象。按 `Ctrl+C` 停止。

## 4. 安装方式二：使用 venv + pip

如果不使用 pipx，可以手动创建虚拟环境：

```bash
python3 -m venv ~/.local/share/argus/.venv
~/.local/share/argus/.venv/bin/pip install ./argus_log_diagnostics-0.1.0-py3-none-any.whl
```

检查安装结果：

```bash
~/.local/share/argus/.venv/bin/argus
```

## 5. 准备配置文件

创建配置目录：

```bash
mkdir -p ~/.config/argus
chmod 700 ~/.config/argus
```

创建 `~/.config/argus/environments.yaml`：

```yaml
environments:
  production:
    provider: ssh
    ssh:
      host: 172.17.162.104
      port: 22
      username: root
      password: "CHANGE_ME"
      connect_timeout: 15
      known_hosts: ~/.ssh/known_hosts
    log_sources:
      appserver:
        path: /var/log/app/app.log
        description: Remote application log
```

保护配置文件权限：

```bash
chmod 600 ~/.config/argus/environments.yaml
```

## 6. 注册到 Codex

如果使用 `pipx` 安装：

```bash
codex mcp add argus \
  --env ARGUS_CONFIG=$HOME/.config/argus/environments.yaml \
  -- argus
```

如果使用 `venv + pip` 安装：

```bash
codex mcp add argus \
  --env ARGUS_CONFIG=$HOME/.config/argus/environments.yaml \
  -- $HOME/.local/share/argus/.venv/bin/argus
```

查看注册结果：

```bash
codex mcp list
```

修改 MCP 配置后，需要重启 Codex。

## 7. 注册到 GitHub Copilot

GitHub Copilot 常见有两种使用入口：

- VS Code Copilot Chat Agent 模式；
- GitHub Copilot CLI。

如果使用 `pipx` 安装，下面配置中的 `command` 可以直接写 `argus`。如果使用
`venv + pip` 安装，请把 `command` 替换为：

```text
$HOME/.local/share/argus/.venv/bin/argus
```

### 7.1 VS Code Copilot Chat

VS Code 的 MCP 配置文件通常放在两个位置之一：

- 当前项目：`.vscode/mcp.json`
- 当前用户：通过命令面板运行 `MCP: Open User Configuration`

如果使用 `pipx` 安装，可以写成：

```json
{
  "servers": {
    "argus": {
      "type": "stdio",
      "command": "argus",
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/.config/argus/environments.yaml"
      }
    }
  }
}
```

如果使用 `venv + pip` 安装，建议使用绝对路径：

```json
{
  "servers": {
    "argus": {
      "type": "stdio",
      "command": "/Users/yourname/.local/share/argus/.venv/bin/argus",
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/.config/argus/environments.yaml"
      }
    }
  }
}
```

请把 `command` 和 `ARGUS_CONFIG` 替换为目标机器上的真实路径。保存后，在
`.vscode/mcp.json` 文件上方点击 `Start`，或从命令面板运行
`MCP: List Servers` 并启动 `argus`。

打开 Copilot Chat，切换到 `Agent` 模式，在工具列表中确认 `argus` 下有以下工具：

- `list_log_sources`
- `list_log_files`
- `search_logs`
- `get_log_context`

### 7.2 Copilot CLI

如果使用 `pipx` 安装，可以用命令添加：

```bash
copilot mcp add argus \
  -e ARGUS_CONFIG=$HOME/.config/argus/environments.yaml \
  -- argus
```

如果使用 `venv + pip` 安装：

```bash
copilot mcp add argus \
  -e ARGUS_CONFIG=$HOME/.config/argus/environments.yaml \
  -- $HOME/.local/share/argus/.venv/bin/argus
```

也可以编辑用户级配置文件 `~/.copilot/mcp-config.json`。

`pipx` 安装示例：

```json
{
  "mcpServers": {
    "argus": {
      "type": "local",
      "command": "argus",
      "args": [],
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/.config/argus/environments.yaml"
      },
      "tools": ["*"]
    }
  }
}
```

`venv + pip` 安装示例：

```json
{
  "mcpServers": {
    "argus": {
      "type": "local",
      "command": "/Users/yourname/.local/share/argus/.venv/bin/argus",
      "args": [],
      "env": {
        "ARGUS_CONFIG": "/Users/yourname/.config/argus/environments.yaml"
      },
      "tools": ["*"]
    }
  }
}
```

如果只希望当前仓库使用 Argus，也可以在项目根目录创建 `.mcp.json` 或
`.github/mcp.json`，内容使用同样的 `mcpServers` 结构。

注意：VS Code Copilot Chat 使用顶层 `servers`；Copilot CLI 使用 `mcpServers`。
两者格式不同，不能直接混用。

## 8. 在 AI 终端中验证

启动 Codex 后输入：

```text
使用 Argus 查看 production 环境中有哪些日志源。
```

然后可以继续请求：

```text
使用 Argus 搜索 production 环境 appserver 日志中的 error、failed、timeout 和 exception。
```

在 VS Code Copilot Chat 的 Agent 模式，或 Copilot CLI 交互模式中，也可以输入同样的提示词。
如果 Copilot 要求确认工具调用，请确认工具名称和参数符合预期后再继续。

## 9. 常见问题

### 找不到 argus 命令

如果使用 `pipx`，确认 PATH 已刷新：

```bash
python3 -m pipx ensurepath
which argus
```

如果使用虚拟环境，MCP 配置中应填写绝对路径：

```text
$HOME/.local/share/argus/.venv/bin/argus
```

### 配置文件找不到

确认 MCP 配置中的 `ARGUS_CONFIG` 是目标机器上的真实路径：

```bash
ls -l ~/.config/argus/environments.yaml
```

### SSH 认证失败

确认：

- `ssh.host`、`ssh.username`、`ssh.password` 正确；
- 目标主机已写入 `~/.ssh/known_hosts`；
- 该账号有日志文件读取权限。

可以先在目标机器上执行：

```bash
ssh-keyscan -H 172.17.162.104 >> ~/.ssh/known_hosts
```
