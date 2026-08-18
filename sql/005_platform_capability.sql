-- 平台能力目录：统一登记 Agent 与非 Agent 可调用能力。
-- 该表只保存受控分发键，不保存 URL、类名、函数名或脚本。
CREATE TABLE IF NOT EXISTS platform_capability (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL,
    capability_type TEXT NOT NULL,
    description TEXT NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    confirmation_policy TEXT NOT NULL DEFAULT 'always',
    permission JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    error_boundary TEXT NOT NULL,
    dispatch_key TEXT NOT NULL,
    retrieval_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_platform_capability_code UNIQUE (code),
    CONSTRAINT chk_platform_capability_type CHECK (
        capability_type IN ('agent', 'chat', 'knowledge_qa', 'policy_decision')
    ),
    CONSTRAINT chk_platform_capability_confirmation_policy CHECK (
        confirmation_policy IN ('always', 'conditional', 'never')
    ),
    CONSTRAINT chk_platform_capability_timeout CHECK (
        timeout_seconds BETWEEN 1 AND 3600
    ),
    CONSTRAINT chk_platform_capability_code_format CHECK (
        code ~ '^[a-z][a-z0-9]*([._-][a-z0-9]+)*$'
    ),
    CONSTRAINT chk_platform_capability_description_not_blank CHECK (
        btrim(description) <> ''
    ),
    CONSTRAINT chk_platform_capability_dispatch_key_format CHECK (
        dispatch_key ~ '^[a-z][a-z0-9]*([._-][a-z0-9]+)*$'
    ),
    CONSTRAINT chk_platform_capability_error_boundary_not_blank CHECK (
        btrim(error_boundary) <> ''
    ),
    CONSTRAINT chk_platform_capability_input_schema_object CHECK (
        jsonb_typeof(input_schema) = 'object'
    ),
    CONSTRAINT chk_platform_capability_output_schema_object CHECK (
        jsonb_typeof(output_schema) = 'object'
    ),
    CONSTRAINT chk_platform_capability_required_fields_array CHECK (
        jsonb_typeof(required_fields) = 'array'
    ),
    CONSTRAINT chk_platform_capability_permission_array CHECK (
        jsonb_typeof(permission) = 'array'
    ),
    CONSTRAINT chk_platform_capability_retrieval_metadata_object CHECK (
        jsonb_typeof(retrieval_metadata) = 'object'
    )
);

CREATE INDEX IF NOT EXISTS idx_platform_capability_enabled_type
    ON platform_capability(enabled, capability_type);
CREATE INDEX IF NOT EXISTS idx_platform_capability_dispatch_key
    ON platform_capability(dispatch_key);

-- 受控初始目录数据。后续管理入口必须复用同一张表，不得新增代码内平行注册表。
INSERT INTO platform_capability (
    code, capability_type, description, input_schema, output_schema,
    required_fields, confirmation_policy, permission, enabled, timeout_seconds,
    error_boundary, dispatch_key, retrieval_metadata
)
VALUES
(
    'tender.generate_bid_skeleton',
    'agent',
    '读取招标文件并生成一份或多份可填写的投标骨架文件。',
    '{"type":"object","properties":{"file_name":{"type":"string"},"content_base64":{"type":"string"},"user_focus":{"type":["string","null"]}}}',
    '{"type":"object","properties":{"analysis":{"type":"object"},"artifacts":{"type":"array"}}}',
    '["file_name","content_base64"]',
    'always',
    '["agent:tender:execute"]',
    TRUE,
    300,
    'tender-agent-v1',
    'agent.tender.generate_bid_skeleton',
    '{"aliases":["招标文件分析","投标骨架","生成投标文件模板"],"examples":["帮我分析这个招标文件并生成投标骨架"],"negative_examples":["只回答制度问题"]}'
),
(
    'tender.extract_bid_format_section',
    'agent',
    '复制用户确认的招标文件格式区间并生成标准资源。',
    '{"type":"object","properties":{"file_name":{"type":"string"},"content_base64":{"type":"string"},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"output_name":{"type":["string","null"]}}}',
    '{"type":"object","properties":{"artifact":{"type":"object"},"block_count":{"type":"integer"}}}',
    '["file_name","content_base64","start_block_id","end_block_id"]',
    'always',
    '["agent:tender:execute"]',
    TRUE,
    300,
    'tender-agent-v1',
    'agent.tender.extract_bid_format_section',
    '{"aliases":["复制投标格式","提取格式区间"],"examples":["把确认的投标格式区间复制出来"]}'
),
(
    'tender.verify_extraction_boundary',
    'agent',
    '返回候选提取边界附近的源文档上下文供 Agent 复核。',
    '{"type":"object","properties":{"file_name":{"type":"string"},"content_base64":{"type":"string"},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"context_radius":{"type":"integer"}}}',
    '{"type":"object","properties":{"context":{"type":"array"}}}',
    '["file_name","content_base64","start_block_id","end_block_id"]',
    'always',
    '["agent:tender:execute"]',
    TRUE,
    120,
    'tender-agent-v1',
    'agent.tender.verify_extraction_boundary',
    '{"aliases":["复核提取边界","检查格式范围"],"examples":["检查这段投标格式的起止范围"]}'
),
(
    'chat.general',
    'chat',
    '使用通用 LLM 处理不需要业务工具的单轮对话。',
    '{"type":"object","properties":{"message":{"type":"string"}}}',
    '{"type":"object","properties":{"answer":{"type":"string"}}}',
    '["message"]',
    'never',
    '[]',
    TRUE,
    120,
    'llm-chat-v1',
    'llm.chat',
    '{"aliases":["普通聊天","通用问答","闲聊"],"examples":["帮我解释一下这个概念"]}'
),
(
    'knowledge.ask',
    'knowledge_qa',
    '基于平台知识库检索制度资料并生成带引用的回答。',
    '{"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer"},"policy_category":{"type":["string","null"]}}}',
    '{"type":"object","properties":{"answer":{"type":"string"},"citations":{"type":"array"}}}',
    '["query"]',
    'always',
    '[]',
    TRUE,
    120,
    'rag-answer-v1',
    'online.knowledge.ask',
    '{"aliases":["制度问答","知识库问答","查制度"],"examples":["根据制度库回答这个问题"]}'
),
(
    'policy.review',
    'policy_decision',
    '依据已登记的政策规则和资料完成结构化政策判断。',
    '{"type":"object","properties":{"scenario_code":{"type":"string"},"submitted_materials":{"type":"array","items":{"type":"string"}},"top_k":{"type":"integer","minimum":1},"document_id":{"type":["integer","null"]},"include_history":{"type":"boolean"}}}',
    '{"type":"object","properties":{"decision":{"type":"object"}}}',
    '["scenario_code","submitted_materials"]',
    'always',
    '[]',
    TRUE,
    120,
    'policy-decision-v1',
    'online.policy_decision.review',
    '{"aliases":["政策判断","规则审核","材料判断"],"examples":["根据政策规则判断这份材料是否符合要求"]}'
)
ON CONFLICT (code) DO NOTHING;
