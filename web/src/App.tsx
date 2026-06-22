import { useMemo, useState } from "react";
import {
  Accordion,
  AccordionItem,
  Button,
  Dropdown,
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderName,
  InlineLoading,
  InlineNotification,
  ProgressIndicator,
  ProgressStep,
  Stack,
  StructuredListBody,
  StructuredListCell,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
  TextArea,
  Theme,
  Tile,
} from "@carbon/react";
import { ArrowRight, Idea, Renew } from "@carbon/react/icons";

import { compileViaAgent, type AgentTrace } from "./lib/a2a";
import {
  type AppMatch,
  compileViaRest,
  getSurface,
  optimizeInducer,
  retrieveSimilar,
  saveCorrection,
  type Surface,
} from "./lib/api";

const REUSE_THRESHOLD = 0.6; // suggest reuse when a prior app's prompt is this similar

const EXAMPLES = [
  { id: "email", label: "Supplier quote email", text: "Write a polite email to a supplier asking for a revised quote for 20 laptops, under $30k, by Friday." },
  { id: "k8s", label: "Kubernetes deployment request", text: "Create a deployment request for a Node.js service on Kubernetes with 3 replicas, staging environment, autoscaling enabled, and logs sent to CloudWatch." },
  { id: "issue", label: "GitHub bug issue", text: "Draft a GitHub issue for a login bug where the password reset email never arrives, priority high." },
];

type Notice = { kind: "success" | "error" | "info" | "warning"; text: string } | null;

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Working…");
  const [traces, setTraces] = useState<AgentTrace[]>([]);
  const [surface, setSurface] = useState<Surface | null>(null);
  const [appId, setAppId] = useState<string | null>(null);
  const [specJson, setSpecJson] = useState("");
  const [via, setVia] = useState<"agent" | "rest" | "reuse" | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [correctionSaved, setCorrectionSaved] = useState(false); // reveals Optimize (just-in-time)
  const [reuse, setReuse] = useState<AppMatch | null>(null); // "reuse existing app?" suggestion

  // Hick's law: the process is externalized so the user never holds it in their head.
  const stepIndex = appId ? 2 : busy ? 1 : 0;

  async function loadSurface(id: string) {
    const s = await getSurface(id);
    setSurface(s);
    setSpecJson(JSON.stringify(s.spec, null, 2));
    setAppId(id);
  }

  async function onReuse(match: AppMatch) {
    setReuse(null);
    setBusy(true);
    setBusyLabel("Loading existing app…");
    try {
      await loadSurface(match.app_id);
      setVia("reuse");
      setTraces([{ label: `Reused existing app: ${match.title}` }]);
    } catch (e) {
      setNotice({ kind: "error", text: `Could not load app: ${(e as Error).message}` });
    }
    setBusy(false);
  }

  async function compile(forceNew = false) {
    const text = prompt.trim();
    if (!text || busy) return;
    setReuse(null);

    // Reuse before recompile: a prior app may already cover this prompt.
    if (!forceNew) {
      try {
        const matches = await retrieveSimilar(text);
        if (matches.length && matches[0].score >= REUSE_THRESHOLD) {
          setReuse(matches[0]);
          return;
        }
      } catch {
        /* retrieval is best-effort; fall through to compile */
      }
    }

    setBusy(true);
    setBusyLabel("Compiling…");
    setNotice(null);
    setTraces([{ label: "Sending prompt to the A2A agent" }]);
    setSurface(null);
    setAppId(null);
    setVia(null);

    let compiledId: string | null = null;
    try {
      const result = await compileViaAgent(text, (p) => {
        setTraces(p.traces);
        if (p.traces.length) setBusyLabel(p.traces[p.traces.length - 1].label + "…");
      });
      compiledId = result.appId;
      if (compiledId) setVia("agent");
    } catch (e) {
      setTraces((t) => [...t, { label: `Agent error: ${(e as Error).message}` }]);
    }

    if (!compiledId) {
      try {
        setBusyLabel("Compiling (deterministic path)…");
        setTraces((t) => [...t, { label: "Falling back to /api/compile" }]);
        compiledId = (await compileViaRest(text)).app_id;
        setVia("rest"); // the small "via rest" tag in the Signature header conveys this
      } catch (e) {
        setNotice({ kind: "error", text: `Compile failed: ${(e as Error).message}` });
      }
    }

    if (compiledId) {
      try {
        await loadSurface(compiledId);
      } catch (e) {
        setNotice({ kind: "error", text: `Loaded app but failed to read surface: ${(e as Error).message}` });
      }
    }
    setBusy(false);
  }

  async function onSaveCorrection() {
    if (!appId) return;
    try {
      await saveCorrection(appId, JSON.parse(specJson));
      setCorrectionSaved(true);
      setNotice({ kind: "success", text: "Saved as training data. Use Optimize (top right) to fold it in." });
    } catch (e) {
      setNotice({ kind: "error", text: `Could not save correction: ${(e as Error).message}` });
    }
  }

  async function onOptimize() {
    try {
      const r = await optimizeInducer();
      setNotice({ kind: r.compiled ? "success" : "info", text: r.message });
    } catch (e) {
      setNotice({ kind: "error", text: `Optimize failed: ${(e as Error).message}` });
    }
  }

  const exampleItems = useMemo(() => EXAMPLES, []);

  return (
    <Theme theme="white">
      <Theme theme="g100">
        <Header aria-label="Prompt2App">
          <span className="brand-mark" aria-hidden="true">
            <Idea size={20} />
          </span>
          <HeaderName href="#" prefix="DSPy">
            Prompt2App
          </HeaderName>
          <HeaderGlobalBar>
            <span className="model-chip">openrouter/openai/gpt-oss-120b</span>
            {/* Just-in-time: Optimize only appears once there's a correction to fold in. */}
            {correctionSaved && (
              <HeaderGlobalAction aria-label="Optimize inducer from corrections" onClick={onOptimize}>
                <Renew size={20} />
              </HeaderGlobalAction>
            )}
          </HeaderGlobalBar>
        </Header>
      </Theme>

      <main className="shell-main">
        <div className="progress-strip">
          <ProgressIndicator currentIndex={stepIndex} spaceEqually>
            <ProgressStep label="Describe" description="Write a prompt" />
            <ProgressStep label="Compile" description="Induce a typed signature" />
            {/* Steps dim until reachable, so the stepper reflects the real sequence. */}
            <ProgressStep label="Fill & run" description="Use the generated app" disabled={!appId} />
            <ProgressStep label="Optimize" description="Correct & re-compile" disabled={!correctionSaved} />
          </ProgressIndicator>
        </div>

        <div className="cols">
          {/* LEFT — input & signature, low visual weight, progressive disclosure */}
          <section className="col col-left">
            <Stack gap={6}>
              <Tile className="panel">
                <h2 className="panel-title">Describe the task</h2>
                <p className="panel-help">
                  A natural-language prompt becomes a reusable, typed app.
                </p>
                <TextArea
                  id="prompt"
                  labelText="Prompt"
                  placeholder="e.g. Write a polite supplier email asking for a revised quote for 20 laptops under $30k by Friday."
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
                <div className="example-row">
                  <Dropdown
                    id="examples"
                    size="md"
                    type="default"
                    titleText=""
                    label="Start from an example…"
                    items={exampleItems}
                    itemToString={(i) => (i ? i.label : "")}
                    selectedItem={null}
                    onChange={({ selectedItem }) => selectedItem && setPrompt(selectedItem.text)}
                  />
                </div>
                <div className="compile-row">
                  {busy ? (
                    <InlineLoading description={busyLabel} status="active" />
                  ) : reuse ? null : (
                    // One filled-primary per view: once an app exists, "Run program"
                    // (in the generated app) is the primary, so Compile steps down.
                    <Button
                      kind={appId ? "tertiary" : "primary"}
                      renderIcon={ArrowRight}
                      onClick={() => compile()}
                      disabled={!prompt.trim()}
                    >
                      {appId ? "Compile again" : "Compile"}
                    </Button>
                  )}
                </div>

                {reuse && !busy && (
                  // Reuse before recompile — a prior app already covers this prompt.
                  <div className="reuse-suggestion">
                    <p className="reuse-title">A similar app already exists</p>
                    <p className="panel-help">
                      “{reuse.title}” · {Math.round(reuse.score * 100)}% match. Reuse it instead of
                      compiling a new one?
                    </p>
                    <div className="reuse-actions">
                      <Button size="sm" kind="primary" onClick={() => onReuse(reuse)}>
                        Reuse this app
                      </Button>
                      <Button size="sm" kind="ghost" onClick={() => compile(true)}>
                        Compile new instead
                      </Button>
                    </div>
                  </div>
                )}
              </Tile>

              {notice && (
                <InlineNotification
                  kind={notice.kind}
                  title={notice.kind === "error" ? "Error" : "Status"}
                  subtitle={notice.text}
                  onCloseButtonClick={() => setNotice(null)}
                  lowContrast
                />
              )}

              {surface && (
                <Accordion>
                  <AccordionItem title="Signature">
                    <div className="sig-head">
                      <Tag type="cool-gray" size="sm">{surface.task_name}</Tag>
                      {via && (
                        <Tag
                          type={via === "agent" ? "green" : via === "reuse" ? "teal" : "blue"}
                          size="sm"
                        >
                          via {via}
                        </Tag>
                      )}
                    </div>
                    <p className="panel-help">{surface.description}</p>

                    <h3 className="sig-label">Inputs</h3>
                    <StructuredListWrapper isCondensed isFlush className="sig-list" aria-label="Inputs">
                      <StructuredListBody>
                        {surface.spec.inputs.map((f: any) => (
                          <StructuredListRow key={f.name}>
                            <StructuredListCell className="sig-name">{f.name}</StructuredListCell>
                            <StructuredListCell className="sig-type">
                              <Tag type="blue" size="sm">{f.type}</Tag>
                            </StructuredListCell>
                          </StructuredListRow>
                        ))}
                      </StructuredListBody>
                    </StructuredListWrapper>

                    <h3 className="sig-label">Outputs</h3>
                    <StructuredListWrapper isCondensed isFlush className="sig-list" aria-label="Outputs">
                      <StructuredListBody>
                        {surface.spec.outputs.map((f: any) => (
                          <StructuredListRow key={f.name}>
                            <StructuredListCell className="sig-name">{f.name}</StructuredListCell>
                            <StructuredListCell className="sig-type">
                              <Tag type="teal" size="sm">{f.type}</Tag>
                            </StructuredListCell>
                          </StructuredListRow>
                        ))}
                      </StructuredListBody>
                    </StructuredListWrapper>
                  </AccordionItem>

                  <AccordionItem title="Edit signature (JSON) → save as correction">
                    <TextArea
                      id="specjson"
                      labelText="App specification"
                      rows={10}
                      value={specJson}
                      onChange={(e) => setSpecJson(e.target.value)}
                    />
                    <div className="compile-row">
                      <Button kind="tertiary" size="md" onClick={onSaveCorrection}>
                        Save correction
                      </Button>
                    </div>
                  </AccordionItem>

                  {traces.length > 0 && (
                    <AccordionItem title={`Agent activity (${traces.length} steps)`}>
                      <ol className="trace">
                        {traces.map((t, i) => (
                          <li key={i}>{t.label}</li>
                        ))}
                      </ol>
                    </AccordionItem>
                  )}
                </Accordion>
              )}
            </Stack>
          </section>

          {/* RIGHT — the generated app gets the visual priority */}
          <section className="col col-right">
            <div className="gen-tile">
              <div className="gen-tile-head">
                <div className="gen-tile-titles">
                  <span className="gen-kicker">Generated app</span>
                  {surface && <span className="gen-title">{surface.title}</span>}
                </div>
                <Tag type="purple" size="sm">MCP App</Tag>
              </div>
              {appId ? (
                <iframe
                  className="gen-frame"
                  title={surface?.title ?? "Generated app"}
                  src={`/app?app_id=${appId}&chrome=0`}
                />
              ) : (
                <div className="gen-empty">
                  <Idea size={32} />
                  <p className="gen-empty-title">Your generated app appears here</p>
                  <p className="panel-help">
                    Compile a prompt to get a typed, runnable app served as an MCP UI resource.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </Theme>
  );
}
