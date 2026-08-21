"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CheckIcon, CopyIcon, DownloadIcon } from "@/components/ui/icons";

export function AnswerMarkdown({ children }: { children: string }) {
  return (
    <div className="answer-markdown mt-2 text-sm leading-6 text-[var(--ink-soft)]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children: linkText, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-[var(--accent)] underline decoration-[var(--line-strong)] underline-offset-2 hover:decoration-current"
            >
              {linkText}
            </a>
          ),
          h1: ({ children: heading }) => <h2>{heading}</h2>,
          h2: ({ children: heading }) => <h2>{heading}</h2>,
          h3: ({ children: heading }) => <h3>{heading}</h3>,
          pre: ({ children: codeBlock }) => <>{codeBlock}</>,
          code: ({ className, children: codeContent, ...props }) => {
            const language = /language-([\w-]+)/.exec(className ?? "")?.[1];
            const content = String(codeContent).replace(/\n$/, "");
            return language
              ? <CodeBlock language={language} content={content} />
              : <code {...props}>{codeContent}</code>;
          },
          table: ({ children: tableContent }) => (
            <div className="overflow-x-auto rounded-[10px] border border-[var(--line)]">
              <table>{tableContent}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ language, content }: { language: string; content: string }) {
  const [copied, setCopied] = useState(false);
  const label = language.toLowerCase() === "bibtex" ? "BibTeX" : language.toUpperCase();

  async function copy() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    globalThis.setTimeout(() => setCopied(false), 1_500);
  }

  function download() {
    const extension = { bibtex: "bib", ris: "ris", latex: "tex" }[language.toLowerCase()] ?? language.toLowerCase();
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `literae-references.${extension}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="code-block my-3 overflow-hidden rounded-[10px] border border-[var(--line)] bg-[var(--panel-2)]">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-3 py-2">
        <span className="text-[11px] font-medium text-[var(--muted)]">{label}</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => void copy()} className="grid size-7 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--ink)]" aria-label={copied ? "Copied" : "Copy code"} title={copied ? "Copied" : "Copy code"}>
            {copied ? <CheckIcon className="size-4" /> : <CopyIcon className="size-4" />}
          </button>
          <button type="button" onClick={download} className="grid size-7 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--ink)]" aria-label={`Download ${label}`} title={`Download ${label}`}>
            <DownloadIcon className="size-4" />
          </button>
        </div>
      </div>
      <pre className="overflow-x-auto p-4"><code>{content}</code></pre>
    </div>
  );
}
