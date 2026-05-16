import readline from "node:readline";

const ESC = "\u001B[";

function color(code, text) {
  return `${ESC}${code}m${text}${ESC}0m`;
}

function bold(text) {
  return color("1", text);
}

function cyan(text) {
  return color("36", text);
}

function dim(text) {
  return color("2", text);
}

function green(text) {
  return color("32", text);
}

function clearBlock(linesWritten) {
  if (!linesWritten) {
    return;
  }

  readline.moveCursor(process.stdout, 0, -linesWritten);
  readline.cursorTo(process.stdout, 0);
  readline.clearScreenDown(process.stdout);
}

function hideCursor() {
  process.stdout.write("\u001B[?25l");
}

function showCursor() {
  process.stdout.write("\u001B[?25h");
}

function renderBlock(lines) {
  process.stdout.write(`${lines.join("\n")}\n`);
  return lines.length;
}

async function readLine(promptText, { defaultValue = "" } = {}) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  try {
    const suffix = defaultValue ? dim(` (${defaultValue})`) : "";
    const answer = await rl.question(`${cyan("?")} ${bold(promptText)}${suffix}\n${dim("> ")} `);
    return answer.trim() || defaultValue;
  } finally {
    rl.close();
  }
}

function withRawMode(run) {
  return new Promise((resolve, reject) => {
    const stdin = process.stdin;
    const wasRaw = Boolean(stdin.isRaw);
    readline.emitKeypressEvents(stdin);
    stdin.setRawMode(true);
    stdin.resume();
    hideCursor();

    const cleanup = () => {
      stdin.removeListener("keypress", onKeypress);
      stdin.setRawMode(wasRaw);
      showCursor();
    };

    const finish = (value) => {
      cleanup();
      resolve(value);
    };

    const fail = (error) => {
      cleanup();
      reject(error);
    };

    const onKeypress = async (_str, key) => {
      try {
        if (key?.sequence === "\u0003") {
          fail(new Error("User cancelled prompt."));
          return;
        }
        const outcome = await run(key, { finish, fail });
        if (outcome === "handled") {
          return;
        }
      } catch (error) {
        fail(error);
      }
    };

    stdin.on("keypress", onKeypress);

    run(null, { finish, fail }).catch(fail);
  });
}

export function printHeader() {
  const lines = [
    "",
    cyan("    ___              __    _ ____"),
    cyan("   /   |  __________/ /_  (_) __/_  __"),
    cyan("  / /| | / ___/ ___/ __ \\/ / /_/ / / /"),
    cyan(" / ___ |/ /  / /__/ / / / / __/ /_/ /"),
    cyan("/_/  |_/_/   \\___/_/ /_/_/_/  \\__, /"),
    cyan("                              /____/"),
    "",
    bold("Architecture setup for this repository"),
    dim("Use arrow keys to move, space to toggle, and enter to confirm."),
    ""
  ];
  process.stdout.write(`${lines.join("\n")}\n`);
}

export async function promptText(label, options = {}) {
  return readLine(label, options);
}

export async function promptSelect(label, options, { initialIndex = 0 } = {}) {
  let selectedIndex = Math.min(Math.max(initialIndex, 0), options.length - 1);
  let linesWritten = 0;

  const render = () => {
    clearBlock(linesWritten);
    const lines = [
      `${cyan("?")} ${bold(label)}`,
      ...options.map((option, index) => {
        const active = index === selectedIndex;
        const pointer = active ? green("›") : " ";
        const title = active ? bold(option.label) : option.label;
        const hint = option.hint ? ` ${dim(`- ${option.hint}`)}` : "";
        return `${pointer} ${title}${hint}`;
      }),
      dim("Use ↑/↓ and press Enter.")
    ];
    linesWritten = renderBlock(lines);
  };

  return withRawMode(async (key, controls) => {
    if (!key) {
      render();
      return "handled";
    }

    if (key.name === "up" || key.name === "k") {
      selectedIndex = (selectedIndex - 1 + options.length) % options.length;
      render();
      return "handled";
    }

    if (key.name === "down" || key.name === "j") {
      selectedIndex = (selectedIndex + 1) % options.length;
      render();
      return "handled";
    }

    if (key.name === "return") {
      clearBlock(linesWritten);
      process.stdout.write(`${green("✔")} ${bold(label)} ${dim("→")} ${options[selectedIndex].label}\n`);
      controls.finish(options[selectedIndex].value);
      return "handled";
    }

    return "handled";
  });
}

export async function promptSingleChoice(label, options, { initialIndex = 0 } = {}) {
  let cursorIndex = Math.min(Math.max(initialIndex, 0), options.length - 1);
  let selectedIndex = Math.min(Math.max(initialIndex, 0), options.length - 1);
  let linesWritten = 0;

  const render = () => {
    clearBlock(linesWritten);
    const lines = [
      `${cyan("?")} ${bold(label)}`,
      ...options.map((option, index) => {
        const active = index === cursorIndex;
        const checked = index === selectedIndex ? green("[x]") : "[ ]";
        const pointer = active ? green("›") : " ";
        const title = active ? bold(option.label) : option.label;
        const hint = option.hint ? ` ${dim(`- ${option.hint}`)}` : "";
        return `${pointer} ${checked} ${title}${hint}`;
      }),
      dim("Use ↑/↓ to move, Space to select, Enter to confirm.")
    ];
    linesWritten = renderBlock(lines);
  };

  return withRawMode(async (key, controls) => {
    if (!key) {
      render();
      return "handled";
    }

    if (key.name === "up" || key.name === "k") {
      cursorIndex = (cursorIndex - 1 + options.length) % options.length;
      render();
      return "handled";
    }

    if (key.name === "down" || key.name === "j") {
      cursorIndex = (cursorIndex + 1) % options.length;
      render();
      return "handled";
    }

    if (key.name === "space") {
      selectedIndex = cursorIndex;
      render();
      return "handled";
    }

    if (key.name === "return") {
      clearBlock(linesWritten);
      process.stdout.write(`${green("✔")} ${bold(label)} ${dim("→")} ${options[selectedIndex].label}\n`);
      controls.finish(options[selectedIndex].value);
      return "handled";
    }

    return "handled";
  });
}

export async function promptMultiSelect(label, options, { initialSelected = [] } = {}) {
  let cursorIndex = 0;
  const selected = new Set(initialSelected);
  let linesWritten = 0;

  const render = () => {
    clearBlock(linesWritten);
    const lines = [
      `${cyan("?")} ${bold(label)}`,
      ...options.map((option, index) => {
        const active = index === cursorIndex;
        const checked = selected.has(option.value) ? green("[x]") : "[ ]";
        const pointer = active ? green("›") : " ";
        const title = active ? bold(option.label) : option.label;
        const hint = option.hint ? ` ${dim(`- ${option.hint}`)}` : "";
        return `${pointer} ${checked} ${title}${hint}`;
      }),
      dim("Use ↑/↓ to move, Space to toggle, Enter to confirm.")
    ];
    linesWritten = renderBlock(lines);
  };

  return withRawMode(async (key, controls) => {
    if (!key) {
      render();
      return "handled";
    }

    if (key.name === "up" || key.name === "k") {
      cursorIndex = (cursorIndex - 1 + options.length) % options.length;
      render();
      return "handled";
    }

    if (key.name === "down" || key.name === "j") {
      cursorIndex = (cursorIndex + 1) % options.length;
      render();
      return "handled";
    }

    if (key.name === "space") {
      const value = options[cursorIndex].value;
      if (selected.has(value)) {
        selected.delete(value);
      } else {
        selected.add(value);
      }
      render();
      return "handled";
    }

    if (key.name === "return") {
      clearBlock(linesWritten);
      const selectedOptions = options.filter((option) => selected.has(option.value));
      process.stdout.write(`${green("✔")} ${bold(label)} ${dim("→")} ${selectedOptions.map((option) => option.label).join(", ")}\n`);
      controls.finish(selectedOptions.map((option) => option.value));
      return "handled";
    }

    return "handled";
  });
}
