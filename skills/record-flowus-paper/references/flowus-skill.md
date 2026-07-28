# FlowUs Skill 连接与使用

本指南依据 [FlowUs MCP & CLI Skill 连接指南](https://flowus.cn/share/52c5848e-83cb-4d39-a4d2-7ad7c1cd1b4e) 整理。

## 选择接入方式

- Agent 同时支持 Skill 和 MCP 时，优先使用 Skill。Skill 按需加载，对话上下文占用更少。
- Agent 只支持 MCP，或用户不希望安装本地程序时，使用 FlowUs MCP。
- 在远程服务器运行或无法打开浏览器时，使用 API 密钥完成 Skill 或 MCP 认证。

## 安装官方 Skill

确认当前环境支持 Agent Skills，并按宿主环境的审批流程运行：

```bash
npx skills add next-space/flowus-skill --skill flowus-cli
```

安装完成后，使用 `$flowus-cli` 处理 FlowUs 工作区的搜索、页面读写、多维表查询和文件上传。若 Agent 没有立即发现新 Skill，重新加载 Skill 列表或重启 Agent 后再检查。

## 授权并验证

1. 首次使用 `$flowus-cli` 时，按照 Skill 的指引发起浏览器授权。
2. 让用户在浏览器中登录 FlowUs，并选择允许访问的工作区、页面和所需权限。
3. 不要要求用户把访问令牌、客户端密钥或其他秘密粘贴到对话中。
4. 授权完成后运行：

```bash
flowus --json whoami
```

确认命令成功返回预期的 FlowUs 身份或工作区后，再执行读取或写入。认证失败时不得声称已连接。

## OAuth 不可用时

引导用户在 FlowUs 中进入“设置 → 已授权应用 → 开发者中心”，创建外部应用：

1. 填写应用名称；重定向 URI 使用 `https://flowus.cn`。
2. 按任务需要勾选读取、插入和更新内容权限。
3. 让用户通过宿主环境支持的安全秘密配置方式设置客户端密钥。不要在聊天、日志、代码或 Git 提交中暴露密钥。
4. 配置完成后再次运行 `flowus --json whoami` 验证。

## MCP 备用方式

仅支持 MCP 时，配置官方服务器：

```text
https://mcp.flowus.cn/message
```

优先使用 MCP OAuth 完成工作区授权。客户端不支持 OAuth 时，使用开发者中心创建的密钥配置旧式 URL `https://mcp.flowus.cn/message?token=<token>`；通过客户端的安全秘密配置写入令牌，不要让用户在聊天中发送真实令牌。

## 在本 Skill 中调用

连接验证成功后，使用 `$flowus-cli` 完成以下操作：

1. 查询目标论文数据库的字段、分类选项和已有记录。
2. 按本 Skill 的查重与分类确认流程决定创建还是更新。
3. 将论文原图、表格截图和整理图先保存到本地，再通过 `$flowus-cli` 上传为 FlowUs 文件或图片块；不要直接写入远程图片 URL。
4. 写入数据库属性、页面正文和原生公式，并在对应位置插入已上传的 FlowUs 图片。
5. 重新读取页面，验证分类、属性、正文、图片和公式确已保存，并确认图片没有使用外链。

若 `$flowus-cli` 暴露的命令或参数与预期不同，以已安装 Skill 的最新说明为准，不要自行编造命令。

## 常见问题

- 浏览器授权失败：确认浏览器已登录 FlowUs，并尝试通过系统默认浏览器重新授权。
- Agent 看不到新 Skill：完全退出并重新打开 Agent，或重新加载 Skill 列表。
- 密钥无效：重新创建密钥，并确认读取、插入和更新权限完整。
- 需要断开连接：删除 Agent 中的 Skill/MCP 配置；使用密钥时，同时在 FlowUs 开发者中心删除对应外部应用。
