declare module 'remark-breaks' {
  import type { Root } from 'mdast';

  export default function remarkBreaks(): (tree: Root) => undefined;
}
