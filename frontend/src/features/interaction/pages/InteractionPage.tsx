import { useState } from "react";
import { Alert, Button, Card, Empty, Input, Space, Tag } from "antd";
import { Check, CircleHelp, RefreshCw, Send, X } from "lucide-react";

import { useIntentProposalResponse, useIntentRecognition } from "../hooks/useIntentInteraction";
import type { InteractionGatewayResult } from "../types";
import styles from "./InteractionPage.module.css";

const statusLabels = {
  needs_clarification: "需要澄清",
  unrecognized: "未识别",
  pending: "等待确认",
  cancelled: "已取消",
  completed: "已完成",
  rejected: "已拒绝",
  failed: "执行失败",
} as const;

const statusColors = {
  needs_clarification: "gold",
  unrecognized: "default",
  pending: "blue",
  cancelled: "default",
  completed: "green",
  rejected: "orange",
  failed: "red",
} as const;

export function InteractionPage() {
  const [userInput, setUserInput] = useState("");
  const [providedInputsText, setProvidedInputsText] = useState("{}");
  const [result, setResult] = useState<InteractionGatewayResult | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const recognition = useIntentRecognition();
  const proposalResponse = useIntentProposalResponse();
  const isWorking = recognition.isPending || proposalResponse.isPending;

  const submitRecognition = async () => {
    const normalizedInput = userInput.trim();
    if (!normalizedInput || isWorking) return;

    let providedInputs: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(providedInputsText || "{}");
      if (!isRecord(parsed)) throw new Error("业务输入必须是 JSON 对象。");
      providedInputs = parsed;
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "业务输入格式无效。");
      return;
    }

    setInputError(null);
    try {
      setResult(await recognition.mutateAsync({ userInput: normalizedInput, providedInputs }));
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "识别请求失败，请稍后重试。");
    }
  };

  const respondToProposal = async (action: "confirm" | "cancel") => {
    const proposalId = result?.proposal?.proposal_id;
    if (!proposalId || isWorking) return;

    try {
      setResult(await proposalResponse.mutateAsync({ proposalId, action }));
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "确认请求失败，请稍后重试。");
    }
  };

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>INTERACTION GATEWAY</span>
          <h1>意图识别</h1>
        </div>
        <Tag color="blue">显式确认</Tag>
      </header>

      <section className={styles.workspace}>
        <Card className={styles.requestCard} variant="borderless">
          <label className={styles.fieldLabel} htmlFor="intent-input">请求内容</label>
          <Input.TextArea
            id="intent-input"
            value={userInput}
            onChange={(event) => setUserInput(event.target.value)}
            placeholder="输入要完成的工作"
            autoSize={{ minRows: 5, maxRows: 10 }}
            disabled={isWorking}
          />

          <label className={styles.fieldLabel} htmlFor="provided-inputs">补充业务输入</label>
          <Input.TextArea
            id="provided-inputs"
            value={providedInputsText}
            onChange={(event) => setProvidedInputsText(event.target.value)}
            placeholder="{}"
            autoSize={{ minRows: 4, maxRows: 8 }}
            disabled={isWorking}
            className={styles.inputsEditor}
          />

          <div className={styles.submitRow}>
            <Button
              type="primary"
              icon={<Send size={15} />}
              onClick={submitRecognition}
              loading={recognition.isPending}
              disabled={!userInput.trim() || isWorking}
            >
              识别请求
            </Button>
            {result && (
              <Button
                type="text"
                icon={<RefreshCw size={14} />}
                onClick={() => setResult(null)}
                disabled={isWorking}
              >
                清除结果
              </Button>
            )}
          </div>
          {inputError && <Alert className={styles.alert} type="error" showIcon message={inputError} />}
        </Card>

        <Card className={styles.resultCard} variant="borderless">
          {result ? (
            <InteractionResult
              result={result}
              isWorking={isWorking}
              onConfirm={() => respondToProposal("confirm")}
              onCancel={() => respondToProposal("cancel")}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无识别结果" />
          )}
        </Card>
      </section>
    </main>
  );
}

function InteractionResult({
  result,
  isWorking,
  onConfirm,
  onCancel,
}: {
  result: InteractionGatewayResult;
  isWorking: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const proposal = result.proposal;

  return (
    <div className={styles.resultContent}>
      <div className={styles.resultHeading}>
        <div>
          <span className={styles.eyebrow}>RESULT</span>
          <h2>处理结果</h2>
        </div>
        <Tag color={statusColors[result.status]}>{statusLabels[result.status]}</Tag>
      </div>

      <Alert
        type={result.status === "failed" ? "error" : result.status === "completed" ? "success" : "info"}
        showIcon
        message={result.message}
      />

      {result.assessment && (
        <section className={styles.detailSection}>
          <div className={styles.detailLabel}>识别能力</div>
          <div className={styles.capabilityValue}>{result.assessment.capability_code ?? "未确定"}</div>
          {result.assessment.missing_fields.length > 0 && (
            <div className={styles.tagGroup}>
              {result.assessment.missing_fields.map((field) => <Tag key={field}>{field}</Tag>)}
            </div>
          )}
          {result.assessment.clarification && (
            <div className={styles.clarification}><CircleHelp size={15} />{result.assessment.clarification}</div>
          )}
        </section>
      )}

      {proposal && result.status === "pending" && (
        <section className={styles.proposalSection}>
          <div className={styles.detailLabel}>待确认能力</div>
          <strong>{proposal.summary}</strong>
          <span>{proposal.confirmation_prompt}</span>
          <Space className={styles.proposalActions} size={8}>
            <Button type="primary" icon={<Check size={15} />} onClick={onConfirm} loading={isWorking}>
              确认执行
            </Button>
            <Button icon={<X size={15} />} onClick={onCancel} disabled={isWorking}>
              取消
            </Button>
          </Space>
        </section>
      )}

      {result.execution_result && (
        <section className={styles.detailSection}>
          <div className={styles.detailLabel}>执行结果</div>
          <pre className={styles.executionResult}>{JSON.stringify(result.execution_result, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
