import { ArrowRight, Bot } from "lucide-react";
import { Link } from "react-router-dom";

import styles from "./TenderPage.module.css";

export function TenderPage() {
  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <span className={styles.eyebrow}>AGENTS / TENDER</span>
          <h1>Tender Agent</h1>
        </div>
        <span className={styles.phaseBadge}>受控调用</span>
      </header>

      <section className={`${styles.panel} ${styles.entryPanel}`}>
        <div className={styles.panelHeader}>
          <div><Bot size={17} /><h2>投标骨架</h2></div>
        </div>
        <Link className={styles.submitButton} to="/chat">
          进入对话 <ArrowRight size={16} />
        </Link>
      </section>
    </main>
  );
}
