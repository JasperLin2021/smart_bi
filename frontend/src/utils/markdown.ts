import { marked, type MarkedOptions } from "marked"
import DOMPurify from "dompurify"

// marked 不做 XSS 过滤，v-html 渲染前必须经 DOMPurify sanitize
export function renderMarkdown(src: string, options?: MarkedOptions): string {
  return DOMPurify.sanitize(marked.parse(src, options) as string)
}
