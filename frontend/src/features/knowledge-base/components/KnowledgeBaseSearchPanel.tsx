import { Search } from "lucide-react";
import { Alert, Button, Card, Empty, Input, Space, Tag, Typography } from "antd";

import type {
  KnowledgeRetrievalMode,
  KnowledgeRetrievalStage,
  KnowledgeSearchResponse,
} from "../types";
import styles from "../pages/KnowledgeBasePage.module.css";

const retrievalModeOptions: Array<{ label: string; value: KnowledgeRetrievalMode }> = [
  { label: "精确向量", value: "exact" },
  { label: "HNSW 向量", value: "hnsw" },
  { label: "多路召回", value: "hybrid" },
];

const topKOptions = [5, 10, 20];

const stageLabels: Record<string, string> = {
  vector_recall: "向量召回",
  keyword_recall: "关键词召回",
  result_fusion: "结果融合",
  rerank: "重排",
  score_filter: "分数过滤",
};

export function KnowledgeBaseSearchPanel({
  query,
  response,
  loading,
  error,
  retrievalMode,
  topK,
  onRetrievalModeChange,
  onTopKChange,
  onQueryChange,
  onSearch,
}: {
  query: string;
  response?: KnowledgeSearchResponse;
  loading: boolean;
  error?: string;
  retrievalMode: KnowledgeRetrievalMode;
  topK: number;
  onRetrievalModeChange: (value: KnowledgeRetrievalMode) => void;
  onTopKChange: (value: number) => void;
  onQueryChange: (value: string) => void;
  onSearch: (value: string) => void;
}) {
  return <div className={styles.searchWorkspace}>
    <div className={styles.searchIntro}>
      <div className={styles.searchIcon}><Search size={20} /></div>
      <div>
        <Typography.Title level={4}>知识检索</Typography.Title>
        <Typography.Text type="secondary">从已发布的制度知识中找到有依据的答案。</Typography.Text>
      </div>
    </div>
    <Card className={styles.searchForm}>
      <div className={styles.searchBar}>
        <Input
          size="large"
          className={styles.searchInput}
          allowClear
          prefix={<Search size={18} aria-hidden="true" />}
          placeholder="例如：申请材料需要哪些证明文件？"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onPressEnter={() => onSearch(query)}
        />
        <Button
          className={styles.searchButton}
          type="primary"
          size="large"
          icon={<Search size={17} />}
          loading={loading}
          onClick={() => onSearch(query)}
        >
          检索
        </Button>
      </div>
      <div className={styles.searchControls}>
        <Space className={styles.searchControlGroup}>
          <Typography.Text className={styles.searchControlLabel}>召回模式</Typography.Text>
          <div className={styles.retrievalMode} role="group" aria-label="召回模式">
            {retrievalModeOptions.map((option) => <Tag.CheckableTag
              key={option.value}
              checked={retrievalMode === option.value}
              onChange={() => onRetrievalModeChange(option.value)}
            >{option.label}</Tag.CheckableTag>)}
          </div>
          <Typography.Text className={styles.searchControlLabel}>返回数量</Typography.Text>
          <div className={styles.topKOptions} role="group" aria-label="返回数量">
            {topKOptions.map((value) => <Tag.CheckableTag
              key={value}
              checked={topK === value}
              onChange={() => onTopKChange(value)}
            >{value}</Tag.CheckableTag>)}
          </div>
        </Space>
        <Space wrap className={`${styles.searchControlGroup} ${styles.recommendationTags}`}>
          <Typography.Text className={styles.searchControlLabel}>推荐问题</Typography.Text>
          <Tag onClick={() => onQueryChange("申请材料需要哪些证明文件？")}>申请材料需要哪些证明文件？</Tag>
          <Tag onClick={() => onQueryChange("证据不足时应该如何处理？")}>证据不足时应该如何处理？</Tag>
        </Space>
      </div>
    </Card>
    {error && <Alert className={styles.searchAlert} type="error" showIcon message={error} />}
    {response && <div className={styles.resultsHeading}>
      <div>
        <Typography.Text type="secondary">检索结果 · {response.strategy}</Typography.Text>
        <Typography.Title level={5}>关于“{response.query}”的检索结果</Typography.Title>
        <RetrievalTrace stages={response.stages} />
      </div>
      <Typography.Text type="secondary">{response.results.length} 个相关片段</Typography.Text>
    </div>}
    {response ? <div className={styles.resultsList}>
      {response.results.map((result, index) => <Card className={styles.resultCard} key={result.id}>
        <div className={styles.resultRank}>0{index + 1}</div>
        <div className={styles.resultBody}>
          <Typography.Text type="secondary">{result.source} · {result.section} · {result.page}</Typography.Text>
          <Typography.Title level={5}>{result.title}</Typography.Title>
          <Typography.Paragraph>{result.text}</Typography.Paragraph>
          <Space>{result.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}</Space>
        </div>
        <Tag color="processing">相关度 {result.score}</Tag>
      </Card>)}
    </div> : <Empty className={styles.searchEmpty} image={Empty.PRESENTED_IMAGE_SIMPLE} description="输入问题开始检索" />}
  </div>;
}

function RetrievalTrace({ stages }: { stages: KnowledgeRetrievalStage[] }) {
  const visibleStages = stages.filter((stage) => stage.name in stageLabels);
  if (!visibleStages.length) return null;

  return <Space wrap size={[6, 4]}>
    {visibleStages.map((stage) => <Tag key={stage.name}>
      {stageLabels[stage.name]} {stage.outputCount ?? 0}
    </Tag>)}
  </Space>;
}
