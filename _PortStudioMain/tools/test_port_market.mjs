import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const code = readFileSync(new URL("../../SoftwarePorts/port-market/main.js", import.meta.url), "utf8");
const SHA = "f".repeat(64);

function setup() {
    const files = new Map();
    const texts = new Map();
    const opened = [];
    const context = vm.createContext({
        app: {}, TR: key => key,
        store: { get: (_key, fallback) => fallback, set() {} },
        sys: { time: () => 900, open: path => { opened.push(path); return true; } },
        fs: {
            exists: path => files.has(path),
            folderGranted: folder => folder === "sdmc:/ports",
            read: path => texts.get(path),
            list: folder => [...files].filter(([p]) => p.startsWith(folder + "/"))
                .map(([p, size]) => ({ name: p.slice(folder.length + 1), size, dir: false })),
            remove: path => files.delete(path),
            rename: (source, target) => {
                if (!files.has(source)) return false;
                files.set(target, files.get(source));
                files.delete(source);
                return true;
            },
        },
        net: {},
    });
    vm.runInContext(code, context);
    const run = expr => vm.runInContext(expr, context);
    return { context, files, texts, opened, run };
}

const original = (name, time, size = 8) => ({
    name, mtime: time, size: String(size), sha1: "f".repeat(40), source: "original",
});

test("archive refresh uses exact items, filters names, and sorts newest uploads first", async () => {
    const { context, run } = setup();
    const fetched = [];
    context.net.fetchJson = async url => {
        fetched.push(url);
        return { result: [
            original("port-1.0.0.nxvapp", 1), original("port-1.1.0.nxvapp", 2),
            original("../private.nxvapp", 3), original("readme.zip", 4),
            original("huge.nxvapp", 5, 2 ** 31), { ...original("derivative.nxvapp", 6), source: "derivative" },
        ] };
    };
    assert.equal(run('itemId("https://archive.org/details/my-ports/")'), "my-ports");
    assert.equal(run('itemId("https://other.example/details/my-ports")'), "");
    await run('sources = ["my-ports"]; refreshArchive()');
    assert.match(fetched[0], /^https:\/\/archive\.org\/metadata\/my-ports\/files/);
    assert.deepEqual(JSON.parse(run("JSON.stringify(archiveRows.map(row => row.version))")), ["1.1.0", "1.0.0"]);
    context.net.fetchJson = async () => { throw new Error("offline"); };
    await run("refreshArchive()");
    assert.equal(run("failedSources"), 1);
    assert.equal(run("archiveRows.length"), 2);
});

test("download stays partial until size matches and opens only its final package path", async () => {
    const { context, files, opened, run } = setup();
    context.fixture = original("port-1.2.3.nxvapp", 3);
    context.net.download = async (url, path, cb, progress) => {
        assert.equal(url, "https://archive.org/download/my-ports/port-1.2.3.nxvapp");
        assert.equal(cb, null);
        progress(8);
        files.set(path, 8);
    };
    await run('archiveRows = archiveFiles("my-ports", {result:[fixture]}); download(archiveRows[0])');
    assert.equal(run("status"), "download.ready");
    assert.equal(run("localPackageReady(archiveRows[0])"), true);
    assert.equal([...files.keys()].some(path => path.endsWith(".part")), false);
    run("openPackage(archiveRows[0])");
    assert.match(opened[0], /^downloads\/my-ports\/[a-f0-9]{40}\/port-1\.2\.3\.nxvapp$/);
});

test("wrong byte count is rejected and cleans up the partial package", async () => {
    const { context, files, run } = setup();
    context.fixture = original("port-1.2.3.nxvapp", 3);
    context.net.download = async (_url, path) => { files.set(path, 4); };
    await run('archiveRows = archiveFiles("my-ports", {result:[fixture]}); download(archiveRows[0])');
    assert.equal(run("status"), "download.failed");
    assert.equal(files.size, 0);
});

test("local catalog accepts per-port subfolders and legacy flat paths", () => {
    const { files, texts, run } = setup();
    texts.set("sdmc:/ports/port-market.tsv", [
        "NXVPORTMARKET\t1",
        `game\tRA2 Yuri Port\t1.2.1\t1024\t${SHA}\tgame/redalert2/com.sonerx7.redalert2-1.2.1-local.nxvapp\t`,
        `game\tCS 1.6\t1.0.1\t512\t${SHA}\tgame/com.sonerx7.cs16-1.0.1-local.nxvapp\t`,
        `game\tBad Traversal\t1.0.0\t512\t${SHA}\tgame/../evil.nxvapp\t`,
    ].join("\n"));
    files.set("sdmc:/ports/game/redalert2/com.sonerx7.redalert2-1.2.1-local.nxvapp", 1024);
    run('localFolder = "sdmc:/ports"; refreshLocal()');
    const paths = JSON.parse(run("JSON.stringify(localRows.map(row => row.path))"));
    assert.deepEqual(paths, [
        "sdmc:/ports/game/redalert2/com.sonerx7.redalert2-1.2.1-local.nxvapp",
        "sdmc:/ports/game/com.sonerx7.cs16-1.0.1-local.nxvapp",
    ]);
    assert.equal(run("localPackageReady(localRows[0])"), true);
    assert.equal(run("localPackageReady(localRows[1])"), false);
});
