#!/usr/bin/env node

const { main } = require("../src/cli");

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
