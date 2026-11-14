# Agent Skills NHB

本仓库收集个人使用的 Agent Skills：

- `write-flowus-research-records`：根据任务类型分别录入论文并生成结构化学习笔记，或依据用户填写的实验信息和材料完善指定的实验报告。连接、证据、排版、图片、公式和回读规则只维护一份。
- `lab-gpu-dispatch`：查看实验室 GPU 池资源，将训练和评估任务分发到指定或空闲服务器，核验运行状态并回传结果。依赖已部署的 `lab-platform` 和本机访问配置。
- `systematic-knowledge-teaching`：面向零基础规划学习大纲，确认后每轮只讲一个小知识点，并在讲解前检查用户提供的学习笔记。

列出或安装仓库中的 skill：

```bash
npx skills add NanHaibei/flowus-recording-rules --list
npx skills add NanHaibei/flowus-recording-rules --skill write-flowus-research-records
```
