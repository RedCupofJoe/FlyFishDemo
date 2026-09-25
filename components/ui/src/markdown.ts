export type Block = { kind: "h1" | "h2" | "h3" | "li" | "p"; text: string };

export function markdownBlocks(markdown: string): Block[] {
  return markdown
    .split("\n")
    .map((line) => {
      if (line.startsWith("### ")) {
        return { kind: "h3" as const, text: line.slice(4) };
      }
      if (line.startsWith("## ")) {
        return { kind: "h2" as const, text: line.slice(3) };
      }
      if (line.startsWith("# ")) {
        return { kind: "h1" as const, text: line.slice(2) };
      }
      if (line.startsWith("- ")) {
        return { kind: "li" as const, text: line.slice(2) };
      }
      if (line.trim()) {
        return { kind: "p" as const, text: line };
      }
      return null;
    })
    .filter((block): block is Block => block !== null);
}
