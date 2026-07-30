# Argus 环境管理说明

本文定义 Argus 的环境配置、日志源白名单、SSH 认证信息保存、安全约束和日常管理流程。

> 当前状态：本地文件 Provider 已实现；SSH Provider 目前仍是占位实现。本文中的 SSH 用户名密码配置是下一阶段的目标设计，相关代码完成前不能用于实际连接。

## 1. 环境的作用

一个 Argus 环境代表一组具有相同访问方式的日志源，例如：

- 本机开发环境；
- 内网测试服务器；
- 内网预发布服务器；
- 内网生产服务器。

Codex 只能向 Argus 提交环境名称和逻辑日志源 ID。服务器地址、登录凭据和真实日志路径由运维人员预先配置，不能由 Codex 临时指定。

推荐的调用边界：

```text
Codex
  -> environment: production
  -> source: order-service
  -> query: timeout OR error
  -> Argus 根据白名单访问固定服务器和固定日志路径
```

## 2. 配置文件

### 2.1 本地实际配置

默认配置文件：

```text
config/environments.yaml
```

也可以通过环境变量指定其他位置：

```bash
export ARGUS_CONFIG=/absolute/path/to/environments.yaml
argus
```

该文件可以保存内网服务器的用户名和密码，但只能保存在运行 Argus 的机器上，不能提交到 Git。

项目的 `.gitignore` 必须包含：

```gitignore
config/environments.yaml
```

设置文件权限：

```bash
chmod 600 config/environments.yaml
```

### 2.2 可提交的示例配置

仓库只提交：

```text
config/environments.example.yaml
```

示例文件中必须使用占位符，不能出现真实密码、生产地址或其他敏感信息。

初始化本地配置：

```bash
cp config/environments.example.yaml config/environments.yaml
chmod 600 config/environments.yaml
```

## 3. 当前支持的本地环境

本地 Provider 配置：

```yaml
environments:
  local:
    provider: local

    log_sources:
      order-service:
        path: fixtures/order-service.log
        description: Order service application log
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `environments` | 是 | 所有环境的根节点 |
| `local` | 是 | 环境名称，可以自定义 |
| `provider` | 是 | 当前设置为 `local` |
| `log_sources` | 是 | 允许访问的日志源白名单 |
| `order-service` | 是 | 暴露给 Codex 的逻辑 source ID |
| `path` | 是 | 本地日志文件路径 |
| `description` | 否 | 日志源用途说明 |

相对路径以项目根目录为基准解析。生产使用建议配置绝对路径，减少启动目录变化带来的歧义。

## 4. SSH 环境目标设计

### 4.1 用户名密码登录

内网环境可以直接在 `environments.yaml` 中保存用户名和密码：

```yaml
environments:
  production:
    provider: ssh

    ssh:
      host: 192.168.10.25
      port: 22
      username: argus-reader
      password: "CHANGE_ME"
      connect_timeout: 10
      known_hosts: ~/.ssh/known_hosts

    log_sources:
      order-service:
        path: /var/log/order-service/application.log
        description: 生产环境订单服务日志

      nginx-error:
        path: /var/log/nginx/error.log
        description: Nginx 错误日志
```

SSH 字段：

| 字段 | 必填 | 默认值 | 说明 |
|---|---:|---:|---|
| `host` | 是 | 无 | 内网服务器 IP 或域名 |
| `port` | 否 | `22` | SSH 端口 |
| `username` | 是 | 无 | SSH 登录用户 |
| `password` | 是 | 无 | SSH 登录密码，仅保存在本地配置中 |
| `connect_timeout` | 否 | `10` | 连接超时秒数 |
| `known_hosts` | 建议 | `~/.ssh/known_hosts` | SSH 主机身份校验文件 |

密码必须使用字符串。密码包含 `#`、`:`、空格、引号或其他 YAML 特殊字符时，应使用引号：

```yaml
password: "p@ss:word#2026"
```

### 4.2 多个 SSH 环境

不同环境分别保存连接信息和日志白名单：

```yaml
environments:
  test:
    provider: ssh
    ssh:
      host: 192.168.10.20
      port: 22
      username: test-reader
      password: "CHANGE_ME"
      connect_timeout: 10
      known_hosts: ~/.ssh/known_hosts
    log_sources:
      order-service:
        path: /opt/apps/order-service/logs/application.log
        description: 测试环境订单服务日志

  production:
    provider: ssh
    ssh:
      host: 192.168.10.25
      port: 22
      username: prod-reader
      password: "CHANGE_ME"
      connect_timeout: 10
      known_hosts: ~/.ssh/known_hosts
    log_sources:
      order-service:
        path: /var/log/order-service/application.log
        description: 生产环境订单服务日志
```

不要在多个环境之间共享可写账号。建议每个环境创建独立的只读用户。

### 4.3 SSH 密钥登录的兼容设计

后续如需同时支持 SSH 密钥，可以采用互斥认证配置：

```yaml
environments:
  production-key:
    provider: ssh
    ssh:
      host: 192.168.10.25
      port: 22
      username: argus-reader
      private_key: ~/.ssh/argus_reader_ed25519
      known_hosts: ~/.ssh/known_hosts
    log_sources:
      order-service:
        path: /var/log/order-service/application.log
        description: 生产环境订单服务日志
```

同一个环境只能配置一种认证方式：

- `password`；或者
- `private_key`。

如果两者同时存在，配置加载应当失败，避免认证方式不明确。

## 5. 日志源管理

### 5.1 source ID 命名

建议采用稳定的小写短横线形式：

```text
order-service
user-service
payment-service
nginx-access
nginx-error
system-messages
```

source ID 是 Codex 调用工具时使用的标识。修改 ID 会导致既有提示词、自动化流程和 cursor 失效。

### 5.2 路径要求

每个日志路径必须满足：

- 由管理员在配置中明确声明；
- 指向普通日志文件；
- 运行 Argus 的用户或远程 SSH 用户拥有只读权限；
- 不允许由 Codex 覆盖；
- 不允许通过 source ID 构造任意路径；
- 不允许包含动态 Shell 表达式。

不安全示例：

```yaml
path: "/var/log/${SERVICE}.log"
path: "/var/log/app.log; cat /etc/passwd"
path: "$(find / -name '*.log')"
```

安全示例：

```yaml
path: /var/log/order-service/application.log
```

### 5.3 最小权限

远程账号建议：

- 只能读取指定日志；
- 不授予 `sudo`；
- 不允许写入、删除或轮转日志；
- 不允许控制服务；
- 不允许读取应用配置、私钥和系统密码文件。

如果日志属于特定用户组，可以只授予日志组读取权限：

```bash
sudo usermod -aG app-logs argus-reader
```

具体权限变更应由系统管理员根据生产环境策略执行。

## 6. 配置校验规则

Argus 启动时应拒绝以下配置：

- `environments` 为空；
- 环境名称重复或格式非法；
- `provider` 不是 `local` 或 `ssh`；
- 环境没有任何 `log_sources`；
- 日志源没有字符串类型的 `path`；
- SSH 环境缺少 `host`、`username` 或认证信息；
- SSH 端口不在 `1–65535` 范围内；
- 超时时间小于或等于零；
- 同时配置密码和私钥；
- `known_hosts` 文件不可用；
- 本地文件不存在、不是普通文件或超过读取限制。

密码不能出现在配置错误信息中。

## 7. 密码保护要求

由于密码直接保存在本地 YAML 中，必须遵循以下规则：

1. `config/environments.yaml` 永远不提交到 Git。
2. 文件权限设置为 `600`。
3. 不在日志中打印完整配置对象。
4. 不在异常信息中输出密码。
5. 不在测试快照、截图或工单中粘贴真实配置。
6. 配置对象的 `repr` 或调试输出必须将密码显示为 `******`。
7. Codex MCP 工具输出不得包含 SSH 配置和密码。
8. 示例文件只允许使用 `CHANGE_ME` 等占位符。
9. 密码泄露后立即修改，不依赖删除 Git 历史来补救。

提交前检查忽略状态：

```bash
git check-ignore -v config/environments.yaml
git status --short
```

如果文件曾经被 Git 跟踪过，需要停止跟踪：

```bash
git rm --cached config/environments.yaml
git commit -m "chore: stop tracking local environment config"
```

这不会删除本地文件，但提交前应再次确认暂存内容中没有密码。

## 8. SSH 主机身份校验

私有网络也应验证远程服务器身份。首次连接前由管理员确认指纹：

```bash
ssh-keyscan -H 192.168.10.25 >> ~/.ssh/known_hosts
ssh-keygen -F 192.168.10.25
```

不要在实现中使用：

```text
StrictHostKeyChecking=no
```

主机密钥变化时应停止连接，由管理员确认服务器是否重装、替换或存在网络风险。

## 9. 在 Codex 中使用环境

注册 Argus MCP Server：

```bash
codex mcp add argus \
  --env ARGUS_CONFIG=/absolute/path/to/Argus/config/environments.yaml \
  -- /absolute/path/to/Argus/.venv/bin/argus
```

进入 Codex 后查看工具：

```text
/mcp
```

列出环境中的日志源：

```text
使用 Argus 查看 production 环境中允许访问的日志源。
```

排查问题：

```text
使用 Argus 分析 production 环境中的 order-service 日志。

搜索 timeout、error、exception 和 failed。
对关键错误读取前后各 15 行。
只报告日志能够证明的事实，并将推测单独标注。
```

Codex 只能使用配置中的环境名和 source ID，不能获取以下信息：

- SSH 密码；
- 完整 SSH 配置；
- 未配置的服务器；
- 未配置的文件路径；
- 任意 Shell 执行能力。

## 10. 配置变更流程

新增环境：

1. 在本地 `environments.yaml` 增加环境。
2. 设置只读账号和日志权限。
3. 确认 SSH 主机指纹。
4. 校验 YAML 格式。
5. 重启 Codex，使 Argus 重新加载和使用配置。
6. 通过 `list_log_sources` 验证。
7. 使用非敏感关键词执行一次查询。

修改密码：

1. 修改服务器账号密码。
2. 更新本地 `environments.yaml`。
3. 重启 Codex。
4. 执行只读查询验证连接。
5. 确认日志和错误输出中没有密码。

删除环境：

1. 确认没有提示词、任务或自动化继续引用该环境。
2. 从 `environments.yaml` 删除环境。
3. 重启 Codex。
4. 停用或删除对应的远程账号。

## 11. 故障排查

### Unknown environment

原因：Codex 使用的环境名不存在。

检查：

```bash
sed -n '1,200p' config/environments.yaml
```

确认环境名大小写完全一致。

### 配置文件不存在

检查 Codex MCP 配置中的 `ARGUS_CONFIG` 是否为绝对路径：

```bash
ls -l /absolute/path/to/config/environments.yaml
```

### SSH authentication failed

检查：

- 用户名和密码是否正确；
- 密码是否因 YAML 特殊字符而被错误解析；
- 账号是否被锁定；
- SSH 服务是否允许密码登录；
- 端口是否正确。

不能把密码加入诊断日志。

### Host key verification failed

说明远程主机不在 `known_hosts` 中，或者指纹发生变化。由管理员验证指纹，不要关闭主机校验。

### Unknown log source

确认 source ID 存在于所选环境的 `log_sources` 中。

### Permission denied

远程账号没有日志读取权限。应调整只读用户或日志用户组权限，不要直接授予 `sudo`。

### SSH reading is not enabled in the MVP

这是当前版本的预期提示，说明 SSH Provider 尚未实现。完成 SSH 配置模型、认证、主机校验、远程读取和测试后才能启用。

## 12. 实现清单

要让本文中的 SSH 环境真正可用，需要完成：

- 扩展 `config.py`，解析 `ssh.host`、`port`、`username`、`password`、`known_hosts` 和超时；
- 对密码字段进行脱敏表示；
- 实现 `SshLogProvider` 的用户名密码认证；
- 验证 SSH 主机密钥；
- 只允许访问配置中的 source ID 和路径；
- 使用参数化调用或 SSH 库，禁止 `shell=True`；
- 增加连接和读取超时；
- 限制远程文件大小、返回行数和单行长度；
- 补充配置校验、认证失败、超时、权限不足和主机校验测试；
- 更新 `environments.example.yaml`；
- 确认所有 MCP 响应都不会泄露凭据。

在这些工作完成之前，SSH 配置属于设计规范，不应宣称为当前可用功能。
