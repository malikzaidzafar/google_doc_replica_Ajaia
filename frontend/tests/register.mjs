// Registers the alias loader so `node --test` can run TS that uses Next.js-style imports.
import { register } from "node:module";

register("./alias-loader.mjs", import.meta.url);
