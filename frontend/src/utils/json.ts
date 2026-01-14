// JSON detection and formatting utilities

/**
 * Check if a string is valid JSON
 */
export function isJSON(str: string | null | undefined): boolean {
  if (!str || typeof str !== 'string') return false;
  const trimmed = str.trim();

  if (
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  ) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}

/**
 * Extract JSON from text (including from markdown code blocks)
 */
export function extractJSON(str: string | null | undefined): string | null {
  if (!str || typeof str !== 'string') return null;
  const trimmed = str.trim();

  // Try direct JSON
  if (isJSON(trimmed)) {
    return trimmed;
  }

  // Try extracting from a *standalone* markdown code block (no surrounding text).
  // This prevents the UI from hiding normal answers that merely include JSON examples.
  const jsonMatch = trimmed.match(/```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```/);
  if (jsonMatch) {
    const fullBlock = jsonMatch[0];
    const extracted = jsonMatch[1];
    const withoutBlock = trimmed.replace(fullBlock, '').trim();
    if (!withoutBlock && isJSON(extracted)) {
      return extracted;
    }
  }

  return null;
}

/**
 * Format JSON with indentation
 */
export function formatJSON(jsonString: string): string {
  try {
    const parsed = JSON.parse(jsonString);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return jsonString;
  }
}

/**
 * Syntax highlight JSON for HTML display
 */
export function syntaxHighlightJSON(jsonString: string): string {
  try {
    const parsed = JSON.parse(jsonString);
    const formatted = JSON.stringify(parsed, null, 2);

    // Simple syntax highlighting
    return formatted.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'json-number';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'json-key';
          } else {
            cls = 'json-string';
          }
        } else if (/true|false/.test(match)) {
          cls = 'json-boolean';
        } else if (/null/.test(match)) {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  } catch {
    return jsonString;
  }
}
