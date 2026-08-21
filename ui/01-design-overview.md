# AetherFlow AI 智能工作台 - 设计规范总览

> 基于 `frontend/` 目录React代码分析生成的完整设计系统文档

## 项目概览

**产品名称**: AetherFlow AI 智能工作台
**产品类型**: 企业级AI工作台系统
**技术栈**: React + TypeScript + Ant Design + Lucide Icons
**设计风格**: 现代化、专业、高效

## 设计系统架构

### 整体布局模式
- **布局类型**: 固定侧边栏 + 响应式主内容区
- **侧边栏宽度**: 252px
- **顶部Header高度**: 72px
- **主内容区背景**: #f5f7fb (浅灰色)
- **侧边栏背景**: 深色渐变 (#111b31 → #0c1529)

### 界面层级结构
```
┌─────────────────────────────────────────────────┐
│                   顶部 Header (72px)              │
├──────────┬──────────────────────────────────────┤
│          │                                       │
│  侧边栏   │           主内容区域                   │
│  252px   │           (响应式宽度)                 │
│          │                                       │
│          │                                       │
└──────────┴──────────────────────────────────────┘
```

## 核心界面模块

### 1. 主工作台布局 (AgentWorkspaceLayout)
**文件**: `frontend/src/layouts/AgentWorkspaceLayout.tsx`

**包含组件**:
- 品牌标识区域 (Sparkles + Logo)
- 导航菜单系统
- 全局搜索功能
- 用户个人资料区域
- 面包屑导航

### 2. 聊天界面 (ChatPage)
**文件**: `frontend/src/features/chat/pages/ChatPage.tsx`

**包含组件**:
- 会话历史列表
- 实时聊天消息流
- 输入组合器和工具栏
- LLM调用信息面板
- 状态指示器和连接管理

### 3. 知识库管理 (KnowledgeBasePage)
**文件**: `frontend/src/features/knowledge-base/pages/KnowledgeBasePage.tsx`

**包含组件**:
- 知识库统计仪表板
- 文档管理表格
- 搜索和过滤面板
- 文档上传系统
- 详情抽屉组件

### 4. Tender Agent界面 (TenderPage)
**文件**: `frontend/src/features/agent/tender/pages/TenderPage.tsx`

AI代理任务管理和分块处理界面

## 设计原则

### 视觉一致性
- 统一的圆角规范: 9px-11px
- 一致的间距系统: 基于8px网格
- 协调的阴影深度: 0-25px扩散

### 交互模式
- 悬停反馈: 背景渐变叠加
- 选中状态: 蓝色高亮 (#82aaff)
- 加载状态: Shimmer效果
- 错误处理: 红色警告提示

### 响应式策略
- 侧边栏固定宽度
- 主内容区弹性布局
- 移动端适配: 1280px以下调整

## 组件库使用

### UI组件库
- **主框架**: Ant Design (Button, Input, Table, Modal等)
- **图标系统**: Lucide React (35+图标)
- **布局系统**: CSS Grid + Flexbox
- **样式方案**: CSS Modules

### 核心图标集
```typescript
// 主要图标使用
Bot, MessageSquare, Home, Library, FileText, Settings,
Sparkles, Search, Plus, ChevronDown, Archive, Send, etc.
```

## 技术实现参考

### 样式变量映射
```css
--primary-color: #4a6cf7;
--success-color: #2aa77c;
--warning-color: #f59e0b;
--error-color: #ef4444;
--text-primary: #1e293b;
--text-secondary: #64748b;
--border-color: #e2e8f0;
```

### 布局模式
- **主容器**: AutoLayout垂直方向
- **导航菜单**: 列表式布局，42px高度项目
- **内容卡片**: 白色背景 + 圆角 + 阴影

## 下一步实现建议

1. **创建Figma组件库**: 基于Ant Design组件创建匹配的设计组件
2. **建立设计变量**: 颜色、间距、字体、圆角、阴影
3. **构建页面模板**: 每个主要界面的Frame模板
4. **创建交互原型**: 导航流程和用户操作路径

---

**文档版本**: 1.0  
**创建日期**: 2025-01-14  
**基于代码**: frontend/src/** 整个React应用分析  
**分析工具**: ZCode AI Agent + 手动代码审查