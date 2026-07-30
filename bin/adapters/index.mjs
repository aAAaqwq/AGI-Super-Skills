import * as claudeCode from "./claude-code.mjs";
import * as codex from "./codex.mjs";
import * as hermes from "./hermes.mjs";
import * as openclaw from "./openclaw.mjs";


const ADAPTERS = new Map(
  [claudeCode, codex, openclaw, hermes].map((adapter) => [
    adapter.ADAPTER_ID,
    adapter,
  ]),
);

export function adapterFor(id) {
  const adapter = ADAPTERS.get(id);
  if (!adapter) throw new Error(`missing external Adapter module: ${id}`);
  if (
    typeof adapter.renderAdapterArtifacts !== "function"
    || typeof adapter.buildConnectionSpec !== "function"
  ) {
    throw new Error(`invalid external Adapter module: ${id}`);
  }
  return adapter;
}

export function adapterIds() {
  return [...ADAPTERS.keys()].sort();
}
