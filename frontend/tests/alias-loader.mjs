// ESM resolve hook: maps `@/x` to the frontend root, adds `.ts` to extensionless relative imports,
// and swaps `react` for a tiny fake so hooks can run without rendering.
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
const candidates = (base) => [base, `${base}.ts`, `${base}/index.ts`];

export async function resolve(specifier, context, next) {
  if (specifier === "react") {
    return { url: new URL("./fake-react.mjs", import.meta.url).href, shortCircuit: true };
  }
  let base;
  if (specifier.startsWith("@/")) base = new URL(specifier.slice(2), root).href;
  else if (specifier.startsWith(".") && context.parentURL) base = new URL(specifier, context.parentURL).href;
  else return next(specifier, context);
  for (const url of candidates(base)) {
    const path = fileURLToPath(url);
    if (existsSync(path) && !path.endsWith("/")) {
      try {
        if ((await import("node:fs")).statSync(path).isFile()) return { url, shortCircuit: true };
      } catch {
        // try the next candidate
      }
    }
  }
  return next(specifier, context);
}
