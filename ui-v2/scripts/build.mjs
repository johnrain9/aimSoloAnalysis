import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const dist = path.join(root, "dist");

async function main() {
  await rm(dist, { recursive: true, force: true });
  await mkdir(dist, { recursive: true });

  const html = await readFile(path.join(root, "index.html"), "utf8");
  const rewritten = html
    .replace("./src/styles.css", "./styles.css")
    .replace("./src/main.js", "./main.js");

  await writeFile(path.join(dist, "index.html"), rewritten, "utf8");
  await writeFile(path.join(dist, "main.js"), await readFile(path.join(root, "src", "main.js"), "utf8"), "utf8");
  await writeFile(path.join(dist, "styles.css"), await readFile(path.join(root, "src", "styles.css"), "utf8"), "utf8");

  console.log(`Built ui-v2 into ${dist}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
