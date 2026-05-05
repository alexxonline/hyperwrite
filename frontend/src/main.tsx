import { JSX, render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { ArrowLeft, BookOpenText, Code2, Eye, FileText, FlaskConical, Loader2, MessageSquarePlus, RefreshCw, Search, Send, Settings2, Sparkles, Trash2 } from "lucide-preact";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import "./styles.css";

type PieceSummary = {
  slug: string;
  title: string;
  created_at: string;
  path: string;
  research_enabled: boolean;
  anti_ai_style_enabled: boolean;
};

type Piece = PieceSummary & {
  markdown: string;
  review: string;
  prompt: string;
  style: string;
  source_files: string[];
  writer_model: string;
  reviewer_model: string;
  research_model: string;
};

type GenerationResponse = {
  piece: Piece;
  review: string;
  research: string;
};

type ModelDefaults = {
  writer_model: string;
  reviewer_model: string;
  research_model: string;
};

const API = import.meta.env.VITE_API_URL ?? "";
const SAVED_ROUTE = "/saved";

type InputEvent = JSX.TargetedEvent<HTMLInputElement, Event>;
type TextareaEvent = JSX.TargetedEvent<HTMLTextAreaElement, Event>;
type View = "desk" | "saved";

function viewFromPath(): View {
  return window.location.pathname === SAVED_ROUTE ? "saved" : "desk";
}

function pathForView(view: View) {
  return view === "saved" ? SAVED_ROUTE : "/";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function safeHref(value: string) {
  if (/^(https?:|mailto:|#|\/)/i.test(value)) return value;
  return "#";
}

function renderInline(text: string, keyPrefix: string): Array<string | JSX.Element> {
  return text
    .split(/(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*)/g)
    .filter(Boolean)
    .map((part, index) => {
      const key = `${keyPrefix}-${index}`;
      const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (link) {
        const href = safeHref(link[2].trim());
        return (
          <a
            key={key}
            className="font-medium text-primary underline underline-offset-4"
            href={href}
            rel={href.startsWith("http") ? "noreferrer" : undefined}
            target={href.startsWith("http") ? "_blank" : undefined}
          >
            {link[1]}
          </a>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={key} className="rounded bg-secondary px-1 py-0.5 font-mono text-[0.9em]">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={key}>{renderInline(part.slice(2, -2), key)}</strong>;
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={key}>{renderInline(part.slice(1, -1), key)}</em>;
      }
      return part;
    });
}

function isMarkdownBlockStart(line: string) {
  return (
    /^#{1,6}\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^```/.test(line) ||
    /^ {0,3}(-{3,}|\*{3,}|_{3,})\s*$/.test(line)
  );
}

function renderHeading(level: number, text: string, key: string) {
  const content = renderInline(text, key);
  const className = "font-semibold tracking-normal text-foreground";
  if (level === 1) return <h1 key={key} className={`${className} text-3xl leading-tight`}>{content}</h1>;
  if (level === 2) return <h2 key={key} className={`${className} text-2xl leading-tight`}>{content}</h2>;
  if (level === 3) return <h3 key={key} className={`${className} text-xl leading-snug`}>{content}</h3>;
  if (level === 4) return <h4 key={key} className={`${className} text-lg leading-snug`}>{content}</h4>;
  if (level === 5) return <h5 key={key} className={`${className} text-base leading-snug`}>{content}</h5>;
  return <h6 key={key} className={`${className} text-sm leading-snug`}>{content}</h6>;
}

function MarkdownPreview({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: JSX.Element[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const key = `md-${index}`;

    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const language = line.slice(3).trim();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(
        <pre key={key} className="overflow-auto rounded-md bg-secondary p-4 font-mono text-sm leading-6 text-secondary-foreground">
          <code aria-label={language ? `${language} code block` : undefined}>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      blocks.push(renderHeading(heading[1].length, heading[2], key));
      index += 1;
      continue;
    }

    if (/^ {0,3}(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push(<hr key={key} className="border-border" />);
      index += 1;
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(
        <blockquote key={key} className="border-l-4 border-primary/40 pl-4 text-muted-foreground">
          {quote.map((quoteLine, quoteIndex) => (
            <p key={`${key}-${quoteIndex}`} className={quoteIndex > 0 ? "mt-2" : undefined}>
              {renderInline(quoteLine, `${key}-${quoteIndex}`)}
            </p>
          ))}
        </blockquote>,
      );
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={key} className="list-disc space-y-2 pl-6">
          {items.map((item, itemIndex) => <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>)}
        </ul>,
      );
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={key} className="list-decimal space-y-2 pl-6">
          {items.map((item, itemIndex) => <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>)}
        </ol>,
      );
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(
      <p key={key} className="leading-7">
        {renderInline(paragraph.join(" "), key)}
      </p>,
    );
  }

  return (
    <article className="flex h-full min-h-[620px] flex-col gap-5 overflow-auto p-6 text-base leading-7 sm:p-8 lg:min-h-[780px]">
      {blocks.length > 0 ? blocks : <p className="text-muted-foreground">No markdown generated yet.</p>}
    </article>
  );
}

function App() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("");
  const [followupPrompt, setFollowupPrompt] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [useResearch, setUseResearch] = useState(false);
  const [useAntiAiStyle, setUseAntiAiStyle] = useState(false);
  const [writerModel, setWriterModel] = useState("");
  const [reviewerModel, setReviewerModel] = useState("");
  const [researchModel, setResearchModel] = useState("");
  const [pieces, setPieces] = useState<PieceSummary[]>([]);
  const [activePiece, setActivePiece] = useState<Piece | null>(null);
  const [review, setReview] = useState("");
  const [research, setResearch] = useState("");
  const [view, setView] = useState<View>(() => viewFromPath());
  const [savedSearch, setSavedSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [applyingReview, setApplyingReview] = useState(false);
  const [followingUp, setFollowingUp] = useState(false);
  const [showMarkdownPreview, setShowMarkdownPreview] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const syncViewToLocation = () => setView(viewFromPath());
    window.addEventListener("popstate", syncViewToLocation);

    fetch(`${API}/api/config/models`)
      .then((response) => response.json())
      .then((defaults: ModelDefaults) => {
        setWriterModel(defaults.writer_model);
        setReviewerModel(defaults.reviewer_model);
        setResearchModel(defaults.research_model);
      })
      .catch(() => setError("Could not load backend model defaults."));

    fetch(`${API}/api/pieces`)
      .then((response) => response.json())
      .then(setPieces)
      .catch(() => setError("Could not load saved pieces."));

    return () => window.removeEventListener("popstate", syncViewToLocation);
  }, []);

  const fileNames = useMemo(() => Array.from(files ?? []).map((file) => file.name), [files]);
  const latestSavedPieces = useMemo(() => pieces.slice(0, 3), [pieces]);
  const filteredSavedPieces = useMemo(() => {
    const query = savedSearch.trim().toLowerCase();
    if (!query) return pieces;
    return pieces.filter((piece) => piece.title.toLowerCase().includes(query));
  }, [pieces, savedSearch]);

  function navigateToView(nextView: View) {
    const nextPath = pathForView(nextView);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setView(nextView);
  }

  async function loadPiece(slug: string) {
    setError("");
    const response = await fetch(`${API}/api/pieces/${slug}`);
    if (!response.ok) {
      setError("Could not open that piece.");
      return;
    }
    const piece = (await response.json()) as Piece;
    setActivePiece(piece);
    setReview(piece.review);
    setResearch("");
    setUseAntiAiStyle(piece.anti_ai_style_enabled);
    navigateToView("desk");
  }

  async function generatePiece(event: Event) {
    event.preventDefault();
    if (!prompt.trim()) {
      setError("Add a prompt before generating.");
      return;
    }
    setLoading(true);
    setError("");
    setReview("");
    setResearch("");
    const form = new FormData();
    form.set("prompt", prompt);
    form.set("style", style);
    form.set("use_research", String(useResearch));
    form.set("use_anti_ai_style", String(useAntiAiStyle));
    if (writerModel.trim()) form.set("writer_model", writerModel.trim());
    if (reviewerModel.trim()) form.set("reviewer_model", reviewerModel.trim());
    if (researchModel.trim()) form.set("research_model", researchModel.trim());
    Array.from(files ?? []).forEach((file) => form.append("files", file));

    try {
      const response = await fetch(`${API}/api/pieces`, { method: "POST", body: form });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "Generation failed.");
      }
      const result = (await response.json()) as GenerationResponse;
      setActivePiece(result.piece);
      setReview(result.review);
      setResearch(result.research);
      setUseAntiAiStyle(result.piece.anti_ai_style_enabled);
      setPieces((current) => [result.piece, ...current]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function applyReviewRewrite() {
    if (!activePiece || !review.trim()) {
      setError("Select a piece with reviewer notes first.");
      return;
    }
    setApplyingReview(true);
    setError("");
    const form = new FormData();
    const selectedReviewerModel = activePiece.reviewer_model || reviewerModel;
    if (selectedReviewerModel.trim()) form.set("reviewer_model", selectedReviewerModel.trim());
    form.set("use_anti_ai_style", String(useAntiAiStyle));

    try {
      const response = await fetch(`${API}/api/pieces/${activePiece.slug}/apply-review`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "Could not apply the review.");
      }
      const piece = (await response.json()) as Piece;
      setActivePiece(piece);
      setReview(piece.review);
      setPieces((current) =>
        current.map((saved) => (saved.slug === piece.slug ? piece : saved)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply the review.");
    } finally {
      setApplyingReview(false);
    }
  }

  async function applyFollowup(event: Event) {
    event.preventDefault();
    if (!activePiece) {
      setError("Select or generate a piece before adding a follow-up.");
      return;
    }
    if (!followupPrompt.trim()) {
      setError("Add a follow-up prompt first.");
      return;
    }
    setFollowingUp(true);
    setError("");
    setReview("");
    const form = new FormData();
    form.set("followup_prompt", followupPrompt.trim());
    form.set("use_anti_ai_style", String(useAntiAiStyle));
    const selectedWriterModel = activePiece.writer_model || writerModel;
    const selectedReviewerModel = activePiece.reviewer_model || reviewerModel;
    if (selectedWriterModel.trim()) form.set("writer_model", selectedWriterModel.trim());
    if (selectedReviewerModel.trim()) form.set("reviewer_model", selectedReviewerModel.trim());

    try {
      const response = await fetch(`${API}/api/pieces/${activePiece.slug}/follow-up`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "Could not apply the follow-up.");
      }
      const piece = (await response.json()) as Piece;
      setActivePiece(piece);
      setReview(piece.review);
      setFollowupPrompt("");
      setPieces((current) =>
        current.map((saved) => (saved.slug === piece.slug ? piece : saved)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply the follow-up.");
    } finally {
      setFollowingUp(false);
    }
  }

  async function deletePiece(piece: PieceSummary) {
    const confirmed = window.confirm(`Delete "${piece.title}"? This cannot be undone.`);
    if (!confirmed) return;
    setError("");
    try {
      const response = await fetch(`${API}/api/pieces/${piece.slug}`, { method: "DELETE" });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ?? "Could not delete that piece.");
      }
      setPieces((current) => current.filter((saved) => saved.slug !== piece.slug));
      if (activePiece?.slug === piece.slug) {
        setActivePiece(null);
        setReview("");
        setResearch("");
        setFollowupPrompt("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete that piece.");
    }
  }

  if (view === "saved") {
    return (
      <main className="min-h-screen bg-background text-foreground">
        <section className="mx-auto flex max-w-[1120px] flex-col gap-5 px-5 py-5">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label="Back to writing desk"
                onClick={() => navigateToView("desk")}
              >
                <ArrowLeft size={18} />
              </Button>
              <div>
                <p className="text-sm text-muted-foreground">Saved files</p>
                <h1 className="text-3xl font-semibold tracking-normal">All saved pieces</h1>
              </div>
            </div>
            <span className="rounded-md border bg-secondary px-3 py-1 text-sm text-secondary-foreground">
              {pieces.length} {pieces.length === 1 ? "file" : "files"}
            </span>
          </header>

          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              size={17}
            />
            <Input
              value={savedSearch}
              onInput={(event: InputEvent) => setSavedSearch(event.currentTarget.value)}
              placeholder="Search by title"
              className="h-12 pl-10"
              aria-label="Search saved files by title"
            />
          </div>
          {error && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="rounded-lg border bg-card shadow-sm">
            <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b px-4 py-3 text-xs font-medium uppercase tracking-normal text-muted-foreground">
              <span>Title</span>
              <span className="hidden sm:block">Created</span>
              <span>Action</span>
            </div>
            <div className="divide-y">
              {filteredSavedPieces.length === 0 && (
                <p className="px-4 py-8 text-sm text-muted-foreground">
                  {pieces.length === 0 ? "No saved pieces yet." : "No saved titles match that search."}
                </p>
              )}
              {filteredSavedPieces.map((piece) => (
                <div
                  key={piece.slug}
                  className="grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 transition-colors hover:bg-accent sm:grid-cols-[1fr_160px_auto]"
                >
                  <button
                    className="min-w-0 text-left"
                    type="button"
                    onClick={() => loadPiece(piece.slug)}
                  >
                    <span className="block truncate text-sm font-medium">{piece.title}</span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">{piece.path}</span>
                  </button>
                  <span className="hidden text-sm text-muted-foreground sm:block">
                    {formatDate(piece.created_at)}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => loadPiece(piece.slug)}
                    >
                      <FileText size={15} />
                      Open
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label={`Delete ${piece.title}`}
                      onClick={() => deletePiece(piece)}
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    );
  }

  const savedPanel = (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2">
          <FileText size={18} /> Saved
        </CardTitle>
        <Button type="button" variant="secondary" size="sm" onClick={() => navigateToView("saved")}>
          View all
        </Button>
      </CardHeader>
      <CardContent className="max-h-80 overflow-auto">
        <div className="flex flex-col gap-2">
          {pieces.length === 0 && <p className="text-sm text-muted-foreground">No saved pieces yet.</p>}
          {latestSavedPieces.map((piece) => (
            <div
              key={piece.slug}
              className="group grid grid-cols-[1fr_40px] overflow-hidden rounded-md border bg-background transition-colors hover:bg-accent"
            >
              <button className="min-w-0 p-3 text-left" type="button" onClick={() => loadPiece(piece.slug)}>
                <span className="block text-sm font-medium">{piece.title}</span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {formatDate(piece.created_at)} {piece.research_enabled ? "with research" : ""}
                </span>
              </button>
              <button
                aria-label={`Delete ${piece.title}`}
                className="flex items-center justify-center border-l text-muted-foreground transition-colors hover:bg-destructive hover:text-destructive-foreground"
                onClick={() => deletePiece(piece)}
                type="button"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  if (!activePiece) {
    return (
      <main className="min-h-screen bg-background text-foreground">
        <section className="mx-auto flex max-w-[760px] flex-col gap-5 px-5 py-6">
          <div className="flex items-center justify-center gap-3 pb-1">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <BookOpenText size={21} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">Hyperwrite</h1>
              <p className="text-sm text-muted-foreground">OpenRouter writing desk</p>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles size={18} /> Compose
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-4" onSubmit={generatePiece}>
                <div className="space-y-2">
                  <Label htmlFor="prompt">Prompt</Label>
                  <Textarea
                    id="prompt"
                    value={prompt}
                    onInput={(event: TextareaEvent) => setPrompt(event.currentTarget.value)}
                    placeholder="Write a sharp, evidence-led essay about..."
                    className="min-h-52 resize-y"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="style">Style</Label>
                  <Input
                    id="style"
                    value={style}
                    onInput={(event: InputEvent) => setStyle(event.currentTarget.value)}
                    placeholder="Concise, editorial, technical, narrative..."
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="files">Source files</Label>
                  <Input
                    id="files"
                    type="file"
                    accept=".md,.markdown,.txt"
                    multiple
                    onChange={(event: InputEvent) => setFiles(event.currentTarget.files)}
                  />
                  {fileNames.length > 0 && (
                    <p className="text-xs text-muted-foreground">{fileNames.join(", ")}</p>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex items-center justify-between rounded-md border bg-secondary/60 px-3 py-2">
                    <Label htmlFor="research" className="flex items-center gap-2">
                      <FlaskConical size={16} /> Research
                    </Label>
                    <Switch
                      id="research"
                      checked={useResearch}
                      onChange={(event: InputEvent) => setUseResearch(event.currentTarget.checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-md border bg-secondary/60 px-3 py-2">
                    <Label htmlFor="anti-ai-style" className="flex items-center gap-2">
                      <Sparkles size={16} /> Human style
                    </Label>
                    <Switch
                      id="anti-ai-style"
                      checked={useAntiAiStyle}
                      onChange={(event: InputEvent) => setUseAntiAiStyle(event.currentTarget.checked)}
                    />
                  </div>
                </div>
                <Button disabled={loading} type="submit" className="w-full">
                  {loading ? <Loader2 className="animate-spin" size={17} /> : <Send size={17} />}
                  {loading ? "Writing" : "Generate piece"}
                </Button>
                {error && (
                  <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </p>
                )}
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 size={18} /> Models
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="writer-model">Writer</Label>
                <Input id="writer-model" value={writerModel} onInput={(event: InputEvent) => setWriterModel(event.currentTarget.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reviewer-model">Reviewer</Label>
                <Input id="reviewer-model" value={reviewerModel} onInput={(event: InputEvent) => setReviewerModel(event.currentTarget.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="research-model">Research</Label>
                <Input id="research-model" value={researchModel} onInput={(event: InputEvent) => setResearchModel(event.currentTarget.value)} />
              </div>
            </CardContent>
          </Card>

          {savedPanel}
        </section>
      </main>
    );
  }

  const sourceFiles = activePiece.source_files?.length
    ? activePiece.source_files.join(", ")
    : "None";
  const details = [
    ["Prompt", activePiece.prompt || "Not recorded"],
    ["Style", activePiece.style || "Not specified"],
    ["Source files", sourceFiles],
    ["Research", activePiece.research_enabled ? "Enabled" : "Off"],
    ["Human style", activePiece.anti_ai_style_enabled ? "Enabled" : "Off"],
  ];
  const modelsUsed = [
    ["Writer", activePiece.writer_model || "Not recorded"],
    ["Reviewer", activePiece.reviewer_model || "Not recorded"],
    ["Research", activePiece.research_model || "Not recorded"],
  ];

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex max-w-[1180px] flex-col gap-5 px-5 py-6">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">Final Markdown</p>
            <h1 className="text-3xl font-semibold tracking-normal">{activePiece.title}</h1>
            <p className="mt-2 max-w-[900px] break-all text-xs text-muted-foreground">{activePiece.path}</p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setActivePiece(null);
              setReview("");
              setResearch("");
              setFollowupPrompt("");
              setError("");
            }}
          >
            <ArrowLeft size={16} />
            New piece
          </Button>
        </header>

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles size={18} /> Compose Details
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
                {details.map(([label, value], index) => (
                  <div
                    key={label}
                    className={index === 0 ? "space-y-1 rounded-md border bg-secondary/40 p-3 sm:col-span-2" : "space-y-1 rounded-md border bg-secondary/40 p-3"}
                  >
                    <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
                    <p className="whitespace-pre-wrap break-words text-sm leading-6">{value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 size={18} /> Models Used
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3">
                {modelsUsed.map(([label, value]) => (
                  <div key={label} className="space-y-1 rounded-md border bg-secondary/40 p-3">
                    <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
                    <p className="break-words font-mono text-xs leading-5">{value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="min-h-[620px] overflow-hidden rounded-lg border bg-card shadow-sm lg:min-h-[780px]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                Written piece
              </p>
              <h2 className="text-lg font-semibold tracking-normal">
                {showMarkdownPreview ? "Preview" : "Markdown source"}
              </h2>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-pressed={showMarkdownPreview}
              onClick={() => setShowMarkdownPreview((current) => !current)}
            >
              {showMarkdownPreview ? <Code2 size={15} /> : <Eye size={15} />}
              {showMarkdownPreview ? "Source" : "Preview"}
            </Button>
          </div>
          {showMarkdownPreview ? (
            <MarkdownPreview markdown={activePiece.markdown} />
          ) : (
            <pre className="h-full min-h-[620px] overflow-auto whitespace-pre-wrap p-6 font-mono text-sm leading-6 sm:p-8 lg:min-h-[780px]">
              {activePiece.markdown}
            </pre>
          )}
        </div>

        <form className="rounded-lg border bg-card p-4 shadow-sm" onSubmit={applyFollowup}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <Label htmlFor="followup-prompt" className="flex items-center gap-2">
              <MessageSquarePlus size={16} /> Follow-up
            </Label>
            <Button
              type="submit"
              variant="secondary"
              size="sm"
              disabled={!followupPrompt.trim() || followingUp}
            >
              {followingUp ? <Loader2 className="animate-spin" size={15} /> : <Send size={15} />}
              Revise
            </Button>
          </div>
          <Textarea
            id="followup-prompt"
            value={followupPrompt}
            onInput={(event: TextareaEvent) => setFollowupPrompt(event.currentTarget.value)}
            placeholder="Ask for a sharper lede, shorter ending, more examples..."
            disabled={followingUp}
            className="min-h-24 resize-y"
          />
        </form>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <CardTitle>Reviewer Notes</CardTitle>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={!review.trim() || applyingReview}
                onClick={applyReviewRewrite}
              >
                {applyingReview ? <Loader2 className="animate-spin" size={15} /> : <RefreshCw size={15} />}
                Apply
              </Button>
            </CardHeader>
            <CardContent>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-secondary p-3 text-xs leading-5 text-secondary-foreground">
                {review || "No review yet."}
              </pre>
            </CardContent>
          </Card>

          {research && (
            <Card>
              <CardHeader>
                <CardTitle>Research Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-secondary p-3 text-xs leading-5 text-secondary-foreground">
                  {research}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </main>
  );
}

render(<App />, document.getElementById("app")!);
