# FlowUs 连接与原生功能

本指南依据 [FlowUs MCP & CLI Skill 连接指南](https://flowus.cn/share/52c5848e-83cb-4d39-a4d2-7ad7c1cd1b4e) 整理。仅在第一次连接、认证失败或需要确认接口能力时完整阅读。

## 选择接入方式

- Agent 同时支持 Skill 和 MCP 时，优先使用 FlowUs 官方 `$flowus-cli` Skill。
- Agent 只支持 MCP，或用户不希望安装本地程序时，使用 FlowUs MCP。
- 在远程服务器运行或无法打开浏览器时，使用 API 密钥完成认证。

## 安装官方 Skill

按宿主环境的审批流程运行：

```bash
npx skills add next-space/flowus-skill --skill flowus-cli
```

安装后使用 `$flowus-cli` 进行工作区搜索、数据库查询、页面读写、文件上传以及原生日期、表格和公式操作。Agent 未立即发现新 Skill 时，重新加载 Skill 列表或重启 Agent。

## 授权和验证

1. 首次使用时按 `$flowus-cli` 指引发起浏览器授权。
2. 让用户在浏览器中登录 FlowUs，选择工作区、页面和必要权限。
3. 不得要求用户在聊天中粘贴访问令牌、客户端密钥或其他秘密。
4. 授权后运行：

```bash
flowus --json whoami
```

确认返回预期身份或工作区后再读取或写入。认证失败时不得声称已连接。

OAuth 不可用时，引导用户在 FlowUs“设置 → 已授权应用 → 开发者中心”创建外部应用，通过宿主环境支持的安全秘密配置方式设置客户端密钥，并授予任务所需的读取、插入和更新权限。

## MCP 备用方式

仅支持 MCP 时配置官方服务器：

```text
https://mcp.flowus.cn/message
```

优先使用 MCP OAuth。客户端不支持 OAuth 时，使用开发者中心密钥配置旧式 URL `https://mcp.flowus.cn/message?token=<token>`，并通过安全秘密配置保存令牌。

## 操作原则

1. 先读取实际字段、属性选项、页面结构和工具最新说明。
2. 使用唯一数据库或页面 ID 限定读取和写入范围。
3. 本地图片通过文件接口上传后再插入，不写入远程图片 URL。
4. 使用实际支持的原生日期、表格和公式接口，不自行编造命令或参数。
5. 写入后重新读取同一目标，核对属性、正文、媒体和原生内容块。
6. 必需能力不可用时不得降级模拟；明确报告未完成项。
