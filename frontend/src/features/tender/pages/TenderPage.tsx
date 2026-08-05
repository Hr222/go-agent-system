import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  LoaderCircle,
  Upload,
  X,
} from "lucide-react";

import { useTenderSkeleton } from "../hooks/useTenderSkeleton";
import type { TenderArtifact } from "../api/tenderApi";
import styles from "./TenderPage.module.css";

export function TenderPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [userFocus, setUserFocus] = useState("");
  const { result, error, isSubmitting, submit, reset } = useTenderSkeleton();

  const onFileChange = (nextFile: File | undefined) => {
    if (!nextFile) return;
    setFile(nextFile);
    reset();
  };

  const onSubmit = async () => {
    if (!file || isSubmitting) return;
    await submit(file, userFocus);
  };

  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <span className={styles.eyebrow}>AGENTS / TENDER</span>
          <h1>Tender Agent</h1>
          <p>从招标文件提取明确要求，生成可继续填写的投标书骨架。</p>
        </div>
        <span className={styles.phaseBadge}>V1 · 仅生成骨架</span>
      </header>

      <section className={styles.workspace}>
        <div className={styles.inputColumn}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <div><FileText size={17} /><h2>招标文件</h2></div>
              <span className={styles.required}>必填</span>
            </div>
            <button
              className={`${styles.dropzone} ${file ? styles.dropzoneSelected : ""}`}
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={isSubmitting}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => onFileChange(event.target.files?.[0])}
              />
              {file ? <FileCheck2 size={28} /> : <Upload size={28} />}
              <strong>{file ? file.name : "选择 DOCX 招标文件"}</strong>
              <span>{file ? `${formatBytes(file.size)} · 已准备分析` : "单个文件不超过 25 MB"}</span>
            </button>
            {file && (
              <div className={styles.fileRow}>
                <div><FileText size={16} /><span>{file.name}</span></div>
                <button
                  className={styles.iconButton}
                  type="button"
                  title="移除文件"
                  onClick={() => { setFile(null); reset(); if (inputRef.current) inputRef.current.value = ""; }}
                  disabled={isSubmitting}
                ><X size={15} /></button>
              </div>
            )}
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <div><FileText size={17} /><h2>关注点</h2></div>
              <span className={styles.optional}>可选</span>
            </div>
            <textarea
              className={styles.focusInput}
              value={userFocus}
              onChange={(event) => setUserFocus(event.target.value)}
              placeholder="例如：重点确认技术标、商务标的文件分线和交付成果归属"
              rows={5}
              disabled={isSubmitting}
            />
            <p className={styles.helper}>V1 只依据当前招标文件，不填充公司资料或行业常识。</p>
          </section>

          <button className={styles.submitButton} type="button" onClick={onSubmit} disabled={!file || isSubmitting}>
            {isSubmitting ? <LoaderCircle className={styles.spin} size={17} /> : <FileCheck2 size={17} />}
            {isSubmitting ? "正在分析并生成" : "生成投标书骨架"}
          </button>

          {error && (
            <div className={styles.errorBox} role="alert">
              <AlertCircle size={18} />
              <div><strong>{error.code}</strong><p>{error.message}</p></div>
              <button type="button" onClick={onSubmit} disabled={!file || isSubmitting}>重试</button>
            </div>
          )}
        </div>

        <section className={styles.resultColumn}>
          {!result && !isSubmitting && !error && <EmptyResult />}
          {isSubmitting && <LoadingResult />}
          {result && <ResultView result={result} />}
        </section>
      </section>
    </main>
  );
}

function EmptyResult() {
  return <div className={styles.emptyResult}><FileCheck2 size={34} /><h2>等待生成结果</h2><p>提交招标文件后，这里会展示关键要求、文件分线和骨架文件。</p></div>;
}

function LoadingResult() {
  return <div className={styles.emptyResult}><LoaderCircle className={styles.spin} size={34} /><h2>正在读取招标要求</h2><p>正在分析文件结构并生成可填写的文档骨架。</p></div>;
}

function ResultView({ result }: { result: NonNullable<ReturnType<typeof useTenderSkeleton>["result"]> }) {
  const { analysis } = result;
  return <div className={styles.resultStack}>
    <div className={styles.resultHeader}><div><span className={styles.eyebrow}>ANALYSIS COMPLETE</span><h2>分析结果</h2></div><span className={analysis.status === "completed" ? styles.successBadge : styles.reviewBadge}>{analysis.status === "completed" ? "已完成" : "待确认"}</span></div>
    <section className={styles.summaryBlock}><span className={styles.resultLabel}>摘要</span><p>{analysis.summary}</p><div className={styles.metaRow}><span>文件分线</span><strong>{packageLabel(analysis.package_type)}</strong><span>输出文件</span><strong>{result.artifacts.length} 个</strong></div></section>
    <section className={styles.resultBlock}><div className={styles.blockTitle}><h3>关键要求</h3><span>{analysis.key_requirements.length}</span></div>{analysis.key_requirements.length ? <div className={styles.requirementList}>{analysis.key_requirements.map((item) => <div className={styles.requirement} key={item.requirement_id}><CheckCircle2 size={15} /><span>{item.title}</span>{item.required && <em>必需</em>}</div>)}</div> : <p className={styles.muted}>招标文件未返回结构化关键要求。</p>}</section>
    <section className={styles.resultBlock}><div className={styles.blockTitle}><h3>文件分线</h3><span>{analysis.outputs.length}</span></div><div className={styles.outputList}>{analysis.outputs.map((output) => <div className={styles.output} key={output.slug}><FileText size={16} /><div><strong>{output.name}</strong><span>{output.document_label}{output.purpose ? ` · ${output.purpose}` : ""}</span></div></div>)}</div></section>
    <section className={styles.resultBlock}><div className={styles.blockTitle}><h3>生成文件</h3><span>{result.artifacts.length}</span></div><div className={styles.artifactList}>{result.artifacts.map((artifact) => <ArtifactRow artifact={artifact} key={artifact.file_name} />)}</div></section>
    {analysis.uncertainties.length > 0 && <div className={styles.warningBox}><AlertCircle size={16} /><div><strong>待确认项</strong>{analysis.uncertainties.map((item) => <p key={item}>{item}</p>)}</div></div>}
  </div>;
}

function ArtifactRow({ artifact }: { artifact: TenderArtifact }) {
  const download = () => {
    const binary = atob(artifact.content_base64);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: artifact.media_type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = artifact.file_name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return <div className={styles.artifactRow}><div><FileText size={17} /><span>{artifact.file_name}</span><small>{formatBytes(artifact.size_bytes)}</small></div><button type="button" title="下载文件" onClick={download}><Download size={16} />下载</button></div>;
}

function formatBytes(value: number) {
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function packageLabel(value: "single_volume" | "multi_volume" | "uncertain") {
  if (value === "single_volume") return "单卷";
  if (value === "multi_volume") return "多卷";
  return "待确认";
}
