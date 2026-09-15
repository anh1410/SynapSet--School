import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

/** Renders question/answer text that may contain inline ($...$) or display ($$...$$)
 *  LaTeX math, matching the mathtext the backend rasterizes into exported PDFs/DOCX.
 *  Drop-in replacement anywhere `question.text` / `correct_answer` is shown today. */
export function LatexText({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          p: ({ children }) => <>{children}</>,
        }}
      >
        {text}
      </ReactMarkdown>
    </span>
  );
}
