# Figma 设计稿实现指南

> 基于 `frontend/` React代码的详细Figma实现步骤

## 实现策略

由于当前Figma MCP工具连接存在技术限制，本指南提供了两种实现方案：

### 方案A: 手动创建（推荐）
### 方案B: 代码辅助设计生成

## 方案A: 手动Figma实现

### 步骤1: 创建设计文件

1. **新建Figma文件**
   - 文件名: "AetherFlow AI 智能工作台"
   - 创建桌面设计文件
   - 设置画板: 1920x1080 (桌面尺寸)

2. **创建页面结构**
   ```
   ├── 🎨 Design System
   ├── 🏠 Homepage (Dashboard)
   ├── 💬 Chat Interface  
   ├── 📚 Knowledge Base
   ├── 🤖 Agent Tender
   └── 📱 Components
   ```

### 步骤2: 建立设计变量

#### 2.1 颜色变量集合
```
集合名: "AetherFlow Colors"
模式: Default

主色系:
- brand/primary: #4a6cf7
- brand/gradient-start: #76a9ff  
- brand/gradient-end: #b59bff

功能色:
- semantic/success: #2aa77c
- semantic/warning: #f59e0b
- semantic/error: #ef4444

中性色:
- gray/bg-dark-start: #111b31
- gray/bg-dark-end: #0c1529
- gray/bg-light: #f5f7fb
- gray/text-primary: #1e293b
- gray/text-secondary: #64748b
- gray/border: #e2e8f0
```

#### 2.2 间距变量集合
```
集合名: "AetherFlow Spacing"

- space/xs: 4px
- space/sm: 8px  
- space/md: 12px
- space/lg: 16px
- space/xl: 24px
- space/2xl: 38px
```

#### 2.3 字体变量集合
```
集合名: "AetherFlow Typography"

- font/family: Inter, system-ui, sans-serif
- font/size/h1: 24px
- font/size/h2: 18px
- font/size/body: 14px
- font/size/caption: 12px
- font/weight/bold: 700
- font/weight/medium: 500
- font/weight/regular: 400
```

### 步骤3: 创建基础组件

#### 3.1 导航组件
**组件名称**: "Navigation/Sidebar Item"

**变体设置**:
- State: Default | Hover | Selected
- Icon: Home | Chat | Bot | Library | Settings

**属性绑定**:
- Label: 文本覆盖
- Icon: INSTANCE_SWAP
- State: VARIANT

#### 3.2 按钮组件  
**组件名称**: "Button/Primary"

**变体设置**:
- Size: Small (24px) | Medium (36px) | Large (44px)
- State: Default | Hover | Active | Disabled

#### 3.3 卡片组件
**组件名称**: "Card/Standard"

**属性**:
- Shadow: 使用效果样式
- Background: 绑定颜色变量
- Radius: 8px

### 步骤4: 构建主界面

#### 4.1 主工作台布局
```
Frame: "Dashboard - Main Layout"
尺寸: 1920x1080
布局: Auto Layout (水平)

子组件:
- Sider: 252px 固定宽度
- Main Content: FILL 剩余空间
```

**Sider结构**:
```
Auto Layout (垂直)
├── Brand Area (93px 高度)
├── Navigation (自动高度)
└── User Profile (固定高度)
```

#### 4.2 聊天界面
```
Frame: "Chat Interface" 
布局: Auto Layout (水平)

左侧面板: 会话列表 (280px)
中间面板: 聊天区域 (自动宽度)  
右侧面板: LLM信息 (320px)
```

**消息气泡组件**:
```
组件名: "Message Bubble"
变体: User | Assistant
属性: Content, Timestamp, Status
```

#### 4.3 知识库界面
```
Frame: "Knowledge Base"
布局: 垂直Auto Layout

├── Header (标题 + 操作)
├── Stats Cards (水平布局)
├── Tabs (切换栏)
└── Content Area (动态内容)
```

### 步骤5: 添加交互原型

#### 5.1 导航流程
```
点击 "对话" → 跳转到 Chat Page
点击 "知识库" → 跳转到 Knowledge Page  
点击 "控制台" → 跳转到 Dashboard
```

#### 5.2 表单交互
```
聚焦输入框 → 显示边框高亮
点击按钮 → 显示按压状态  
悬停卡片 → 显示阴影加深
```

## 方案B: 代码辅助生成

### 使用现有工具

#### 1. React to Figma插件
- **工具**: React to Figma Plugin
- **方法**: 直接导入React组件代码
- **优点**: 保持代码和设计同步

#### 2. CSS解析工具
- **工具**: Figma CSS Parser
- **方法**: 从CSS Module文件解析样式
- **步骤**: 
  1. 导入 `*.module.css` 文件
  2. 自动创建对应的Figma样式
  3. 应用到对应组件

#### 3. 设计转换工具
- **工具**: Zeplin, Figma to Code
- **方法**: 从代码生成设计规格
- **流程**: React组件 → HTML/CSS → Figma转换

## 实现检查清单

### 基础设置
- [ ] 创建设计文件和页面结构
- [ ] 建立颜色、间距、字体变量
- [ ] 创建组件库框架

### 核心组件
- [ ] 导航系统 (侧边栏菜单)
- [ ] 顶部导航栏
- [ ] 按钮系统 (主要/次要/图标按钮)
- [ ] 卡片组件
- [ ] 表单组件 (输入框、下拉菜单)

### 页面布局
- [ ] 主工作台布局
- [ ] 聊天界面
- [ ] 知识库管理界面
- [ ] Tender Agent界面

### 交互设计
- [ ] 导航流程原型
- [ ] 悬停状态设计
- [ ] 加载状态动画
- [ ] 错误处理状态

### 响应式适配
- [ ] 大屏布局 (1920px+)
- [ ] 中屏布局 (1280px-1920px)
- [ ] 小屏布局 (<1280px)

## 质量标准

### 视觉一致性
- 所有颜色必须使用设计变量
- 间距必须遵循8px网格系统
- 字体大小必须使用预定义变量
- 圆角半径必须标准化

### 组件复用性
- 所有可复用元素必须设为组件
- 组件变体必须完整覆盖状态
- 组件属性必须可配置

### 可维护性
- 命名规范统一
- 层级结构清晰
- 样式来源可追溯

## 导出规范

### 切图导出
- 格式: PNG (2x, 3x)
- 命名: `组件名_状态@尺寸倍数.png`
- 范围: 仅导出自定义图标和装饰元素

### 标注导出
- 格式: PDF
- 内容: 尺寸、间距、颜色代码
- 精度: 像素级

### 交接文件
- 设计文件: 完整的Figma源文件
- 组件库: 独立的组件库文件
- 规范文档: 本设计规范文档

---

**实施优先级**: P0 (核心布局) > P1 (组件系统) > P2 (交互原型)  
**预估时间**: 核心布局2-4小时，完整系统8-12小时  
**技能要求**: 熟悉Figma组件、变量、AutoLayout功能  
**更新日期**: 2025-01-14