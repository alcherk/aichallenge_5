// Markdown formatting utilities

/**
 * Format markdown text to HTML
 * This is a basic implementation - for production use react-markdown
 */
export function formatMarkdownBasic(text: string): string {
  if (!text) return '';

  let html = text;

  // Code blocks first (before escaping)
  html = html.replace(/```([\s\S]*?)```/g, (_match, code) => {
    const escaped = escapeHtml(code);
    return '<pre><code>' + escaped + '</code></pre>';
  });

  // Inline code
  html = html.replace(/`([^`\n]+)`/g, (_match, code) => {
    const escaped = escapeHtml(code);
    return '<code>' + escaped + '</code>';
  });

  // Escape remaining HTML (preserve code blocks)
  const parts = html.split(/(<pre><code>[\s\S]*?<\/code><\/pre>|<code>[\s\S]*?<\/code>)/);
  html = parts
    .map((part) => {
      if (part.startsWith('<pre><code>') || part.startsWith('<code>')) {
        return part; // Already processed
      }
      return escapeHtml(part);
    })
    .join('');

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/_(.*?)_/g, '<em>$1</em>');

  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>'
  );

  // Lists
  html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
  html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
  html = html.replace(/^(\d+)\. (.*$)/gim, '<li>$2</li>');

  // Wrap consecutive list items in ul
  html = html.replace(/(<li>.*<\/li>(\n|$))+/gim, '<ul>$&</ul>');

  // Line breaks - double newline becomes paragraph break
  html = html
    .split(/\n\n+/)
    .map((para) => {
      if (para.trim().startsWith('<')) {
        return para; // Already has HTML tags
      }
      para = para.replace(/\n/g, '<br>');
      return para.trim() ? '<p>' + para + '</p>' : '';
    })
    .join('');

  return html;
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
