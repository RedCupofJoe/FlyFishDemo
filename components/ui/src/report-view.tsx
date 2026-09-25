import { Title } from "@patternfly/react-core";
import { markdownBlocks } from "./markdown";

export function ReportView({ text }: { text: string }) {
  return (
    <div>
      {markdownBlocks(text).map((block, index) => {
        if (block.kind === "h1") {
          return (
            <Title key={index} headingLevel="h2">
              {block.text}
            </Title>
          );
        }
        if (block.kind === "h2") {
          return (
            <Title key={index} headingLevel="h3">
              {block.text}
            </Title>
          );
        }
        if (block.kind === "h3") {
          return (
            <Title key={index} headingLevel="h4">
              {block.text}
            </Title>
          );
        }
        if (block.kind === "li") {
          return <p key={index}>• {block.text}</p>;
        }
        return <p key={index}>{block.text}</p>;
      })}
    </div>
  );
}
