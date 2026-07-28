# FlowUs 连接与原生功能

本指南依据 [FlowUs MCP & CLI Skill 连接指南](https://flowus.cn/share/52c5848e-83cb-4d39-a4d2-7ad7c1cd1b4e) 整理。

## 选择接入方式

- Agent 同时支持 Skill 和 MCP 时，优先使用 FlowUs 官方 `$flowus-cli` Skill。
- Agent 只支持 MCP，或用户不希望安装本地程序时，使用 FlowUs MCP。
- 在远程服务器运行或无法打开浏览器时，使用 API 密钥完成 Skill 或 MCP 认证。

## 安装官方 Skill

确认当前环境支持 Agent Skills，并按宿主环境的审批流程运行：

```bash
npx skills add next-space/flowus-skill --skill flowus-cli
```

安装完成后，使用 `$flowus-cli` 处理 FlowUs 工作区搜索、页面读写、多维表查询、文件上传和原生内容块。若 Agent 没有立即发现新 Skill，重新加载 Skill 列表或重启 Agent 后再检查。

## 授权并验证

1. 首次使用 `$flowus-cli` 时，按 Skill 指引发起浏览器授权。
2. 让用户在浏览器中登录 FlowUs，并选择允许访问的工作区、页面和必要权限。
3. 不要要求用户把访问令牌、客户端密钥或其他秘密粘贴到对话中。
4. 授权完成后运行 `flowus --json whoami`，确认返回预期身份或工作区后再读写。

OAuth 不可用时，引导用户在 FlowUs“设置 → 已授权应用 → 开发者中心”创建外部应用，通过宿主环境的安全秘密配置方式设置客户端密钥。不得在聊天、日志、代码或 Git 提交中暴露密钥。

仅支持 MCP 时，配置官方服务器：

```text
https://mcp.flowus.cn/message
```

优先使用 MCP OAuth。客户端不支持 OAuth 时，使用开发者中心创建的密钥配置旧式 URL `https://mcp.flowus.cn/message?token=<token>`，并通过客户端的安全秘密配置保存令牌。

## 在实验报告 Skill 中调用

连接成功后：

1. 使用唯一页面 ID 读取用户指定的实验报告，并将所有写操作限定到该页面或其子块。
2. 在写入前检查用户是否已填写开始时间、实验原因和实验内容。
3. 先读取工具的最新说明，确认日期、表格、公式、图片上传和页面回读接口的实际参数，不要自行编造命令。
4. 将本地图片或本地生成的图表通过文件接口上传，再以 FlowUs 图片块插入；不要写入远程图片 URL。
5. 使用 FlowUs 原生表格和公式接口，不要用 Markdown 或普通文本模拟。
6. 正文完成并回读成功后，使用原生【日期】接口保留开始时间并补充完成时间。
7. 再次读取同一页面，核对页面 ID、正文、图片、表格、公式和日期范围。

任何必需的原生能力不可用时，不要改用普通文本或外链降级；明确说明相应内容尚未完成。
