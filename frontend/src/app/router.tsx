import { Navigate, createBrowserRouter } from "react-router-dom";

import { AgentWorkspaceLayout } from "../layouts/AgentWorkspaceLayout";
import { ChatPage } from "../features/chat/pages/ChatPage";
import { KnowledgeBasePage } from "../features/knowledge-base/pages/KnowledgeBasePage";
import { MockWorkspacePage } from "../features/mock-workspace/pages/MockWorkspacePage";
import { TenderPage } from "../features/tender/pages/TenderPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AgentWorkspaceLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <MockWorkspacePage kind="dashboard" /> },
      { path: "chat", element: <ChatPage /> },
      { path: "agents", element: <MockWorkspacePage kind="agents" /> },
      { path: "agents/tender", element: <TenderPage /> },
      { path: "agents/tender/tasks/:taskId", element: <MockWorkspacePage kind="task" /> },
      { path: "agents/tender/tasks/:taskId/skeleton", element: <MockWorkspacePage kind="skeleton" /> },
      { path: "workflow", element: <MockWorkspacePage kind="workflow" /> },
      { path: "knowledge-bases", element: <KnowledgeBasePage /> },
      { path: "knowledge-bases/:knowledgeBaseId", element: <KnowledgeBasePage /> },
      { path: "knowledge-bases/:knowledgeBaseId/search", element: <KnowledgeBasePage /> },
      { path: "docs", element: <MockWorkspacePage kind="docs" /> },
      { path: "settings", element: <MockWorkspacePage kind="settings" /> },
      { path: "*", element: <Navigate to="/dashboard" replace /> },
    ],
  },
]);
