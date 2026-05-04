import { JSX, render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { BookOpenText, FileText, FlaskConical, Loader2, Send, Settings2, Sparkles } from "lucide-preact";

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
};

type Piece = PieceSummary & {
  markdown: string;
  review: string;
  prompt: string;
};

type GenerationResponse = {
  piece: Piece;
  review: string;
  research: string;
};

const API = import.meta.env.VITE_API_URL ?? "";

type InputEvent = JSX.TargetedEvent<HTMLInputElement, Event>;
type TextareaEvent = JSX.TargetedEvent<HTMLTextAreaElement, Event>;

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function App() {
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [useResearch, setUseResearch] = useState(false);
  const [writerModel, setWriterModel] = useState("openai/gpt-5");
  const [reviewerModel, setReviewerModel] = useState("anthropic/claude-sonnet-4.5");
  const [researchModel, setResearchModel] = useState("perplexity/sonar-pro-search");
  const [pieces, setPieces] = useState<PieceSummary[]>([]);
  const [activePiece, setActivePiece] = useState<Piece | null>(null);
  const [review, setReview] = useState("");
  const [research, setResearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/pieces`)
      .then((response) => response.json())
      .then(setPieces)
      .catch(() => setError("Could not load saved pieces."));
  }, []);

  const fileNames = useMemo(() => Array.from(files ?? []).map((file) => file.name), [files]);

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
    form.set("writer_model", writerModel);
    form.set("reviewer_model", reviewerModel);
    form.set("research_model", researchModel);
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
      setPieces((current) => [result.piece, ...current]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto grid max-w-[1500px] gap-6 px-5 py-5 lg:grid-cols-[390px_1fr_340px]">
        <aside className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <BookOpenText size={22} />
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
                    className="min-h-44 resize-y"
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
                <Button disabled={loading} type="submit" className="w-full">
                  {loading ? <Loader2 className="animate-spin" size={17} /> : <Send size={17} />}
                  {loading ? "Writing" : "Generate piece"}
                </Button>
                {error && <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
              </form>
            </CardContent>
          </Card>
        </aside>

        <section className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-muted-foreground">Final Markdown</p>
              <h2 className="text-3xl font-semibold tracking-normal">
                {activePiece?.title ?? "No piece selected"}
              </h2>
            </div>
            {activePiece && (
              <span className="rounded-md border bg-secondary px-3 py-1 text-xs text-secondary-foreground">
                {activePiece.path}
              </span>
            )}
          </div>
          <div className="min-h-[460px] overflow-hidden rounded-lg border bg-card lg:min-h-[760px]">
            <pre className="h-full min-h-[460px] overflow-auto whitespace-pre-wrap p-6 font-mono text-sm leading-6 lg:min-h-[760px]">
              {activePiece?.markdown ?? "Awaiting Markdown."}
            </pre>
          </div>
        </section>

        <aside className="flex flex-col gap-4">
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

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText size={18} /> Saved
              </CardTitle>
            </CardHeader>
            <CardContent className="max-h-80 overflow-auto">
              <div className="flex flex-col gap-2">
                {pieces.length === 0 && <p className="text-sm text-muted-foreground">No saved pieces yet.</p>}
                {pieces.map((piece) => (
                  <button
                    key={piece.slug}
                    className="rounded-md border bg-background p-3 text-left transition-colors hover:bg-accent"
                    onClick={() => loadPiece(piece.slug)}
                  >
                    <span className="block text-sm font-medium">{piece.title}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {formatDate(piece.created_at)} {piece.research_enabled ? "with research" : ""}
                    </span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Reviewer Notes</CardTitle>
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
        </aside>
      </section>
    </main>
  );
}

render(<App />, document.getElementById("app")!);
