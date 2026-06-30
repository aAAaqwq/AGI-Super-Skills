#!/usr/bin/env node
import { main } from '../cli.mjs';

main(process.argv.slice(2)).catch((err) => {
  const msg = err && typeof err === 'object' && 'stack' in err ? err.stack : String(err);
  console.error(msg);
  process.exitCode = 1;
});
