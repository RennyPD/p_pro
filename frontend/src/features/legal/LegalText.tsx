import type { ReactNode } from "react";

/** **bold** inside a line, as React elements (never raw HTML). */
function inline(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, index) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={index}>{part.slice(2, -2)}</strong>
      ) : (
        part
      ),
    );
}

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map(cell => cell.trim());

/**
 * The small Markdown subset of the legal texts: headings, paragraphs, lists,
 * tables and bold. Enough for app/legal/*.md without a Markdown library.
 */
export function LegalText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.split("\n");
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const key = `b${index}`;
    if (!line.trim()) {
      index += 1;
    } else if (line.startsWith("# ")) {
      blocks.push(<h1 key={key}>{inline(line.slice(2))}</h1>);
      index += 1;
    } else if (line.startsWith("## ")) {
      blocks.push(<h2 key={key}>{inline(line.slice(3))}</h2>);
      index += 1;
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index].startsWith("|")) {
        if (!/^\|[\s|:-]+\|$/.test(lines[index].trim())) rows.push(cells(lines[index]));
        index += 1;
      }
      const [head, ...body] = rows;
      blocks.push(
        <div key={key} className="table-scroll">
          <table>
            <thead>
              <tr>
                {head.map(cell => (
                  <th key={cell}>{inline(cell)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{inline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else if (/^(- |\d+\. )/.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const items: string[] = [];
      while (index < lines.length && /^(- |\d+\. )/.test(lines[index])) {
        items.push(lines[index].replace(/^(- |\d+\. )/, ""));
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={key}>
          {items.map((item, itemIndex) => (
            <li key={itemIndex}>{inline(item)}</li>
          ))}
        </List>,
      );
    } else {
      const paragraph: string[] = [];
      while (
        index < lines.length &&
        lines[index].trim() &&
        !/^(#|\||- |\d+\. )/.test(lines[index])
      ) {
        paragraph.push(lines[index]);
        index += 1;
      }
      blocks.push(<p key={key}>{inline(paragraph.join(" "))}</p>);
    }
  }
  return <div className="legal-text">{blocks}</div>;
}
