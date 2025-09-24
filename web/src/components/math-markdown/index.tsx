import DOMPurify from 'dompurify';
import { memo, useMemo } from 'react';
import type { Components } from 'react-markdown';
import Markdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

import 'katex/dist/katex.min.css';

interface MathMarkdownProps {
  content?: string | null;
  className?: string;
  components?: Components;
}

const MathMarkdown = ({
  content,
  className,
  components,
}: MathMarkdownProps) => {
  const sanitizedContent = useMemo(
    () => DOMPurify.sanitize(content ?? ''),
    [content],
  );

  return (
    <Markdown
      className={className}
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, rehypeKatex]}
      components={components}
    >
      {sanitizedContent}
    </Markdown>
  );
};

export default memo(MathMarkdown);
