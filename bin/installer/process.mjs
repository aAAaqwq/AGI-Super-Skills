import { spawnSync } from "node:child_process";


const UNSAFE_CMD_COMMAND = /[\0\r\n"%!^&|<>]/u;
const SAFE_CMD_ARGUMENT = /^[\p{L}\p{N}_./:@+=,\\-]+$/u;
const BARE_CMD_COMMAND = /^[\p{L}\p{N}_.@+=,-]+$/u;

function windowsCommandLine(command, args) {
  if (typeof command !== "string" || !command || UNSAFE_CMD_COMMAND.test(command)) {
    throw new Error(`unsafe Windows CLI command: ${command || "<missing>"}`);
  }
  for (const argument of args) {
    if (typeof argument !== "string" || !SAFE_CMD_ARGUMENT.test(argument)) {
      throw new Error(`unsafe Windows CLI argument: ${String(argument)}`);
    }
  }
  const suffix = args.length ? ` ${args.join(" ")}` : "";
  // A quoted PATH-resolved batch name without its .cmd suffix can make cmd.exe
  // expand %~dp0 relative to the caller's working directory. Bare command names
  // contain no shell metacharacters and do not need quoting; explicit paths stay
  // quoted so spaces and parentheses remain literal.
  if (BARE_CMD_COMMAND.test(command)) return `${command}${suffix}`;
  return `""${command}"${suffix}"`;
}

export function spawnCli(command, args, options = {}) {
  if (!Array.isArray(args)) throw new Error("CLI arguments must be an array");
  const {
    platform: targetPlatform = process.platform,
    comspec,
    ...spawnOptions
  } = options;
  if (targetPlatform !== "win32") return spawnSync(command, args, spawnOptions);

  const commandProcessor = comspec
    || spawnOptions.env?.ComSpec
    || spawnOptions.env?.COMSPEC
    || process.env.ComSpec
    || process.env.COMSPEC
    || "cmd.exe";
  return spawnSync(
    commandProcessor,
    ["/d", "/s", "/c", windowsCommandLine(command, args)],
    {...spawnOptions, windowsVerbatimArguments: true},
  );
}
