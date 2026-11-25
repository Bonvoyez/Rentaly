import { useEffect, useRef, useState } from "react";
import boardImage from "../../assets/figma/board-ready.jpeg";
import completeImage from "../../assets/figma/complete-4.png";
import manualImage from "../../assets/figma/manual-3.png";
import { Button, InspectionCheck, ProgressBar, SystemStatus, ThemeToggle } from "../../components/ui";
import { assertNever, type KioskView, type Telemetry } from "../../domain/inspection";
import { subscribeToTelemetry, type TelemetryConnection, type TelemetrySession } from "../../services/telemetry";

function initialView(): KioskView {
  const state = new URLSearchParams(window.location.search).get("state");
  return state === "ocr" ||
    state === "led" ||
    state === "ai" ||
    state === "pass" ||
    state === "complete" ||
    state === "reposition" ||
    state === "fail" ||
    state === "manual" ||
    state === "error"
    ? state
    : "ready";
}
const nextView: Readonly<Record<KioskView, KioskView>> = {
  ready: "ocr",
  ocr: "led",
  led: "ai",
  ai: "pass",
  pass: "complete",
  complete: "ready",
  reposition: "ocr",
  fail: "ready",
  manual: "ready",
  error: "ready",
};
type FailureTarget = "pwr-led" | "exterior";
function viewForTelemetry(telemetry: Telemetry): KioskView {
  switch (telemetry.stage) {
    case "MOUNTED":
    case "STABILIZING":
    case "BLUR_CHECK":
    case "OCR":
      return "ocr";
    case "LED_CHECK":
      return "led";
    case "AI_INFERENCE":
      return "ai";
    case "COMPLETED":
      return telemetry.primaryVerdict === "FAIL" ? "fail" : "pass";
    case "REPOSITION":
      return "reposition";
    case "ERROR":
      return "error";
    case "MANUAL_RETURN":
      return "manual";
    default:
      return assertNever(telemetry);
  }
}

export function KioskPage() {
  const [view, setView] = useState<KioskView>(initialView);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [connection, setConnection] = useState<TelemetryConnection>("disconnected");
  const [failureTarget, setFailureTarget] = useState<FailureTarget>("exterior");
  const [captureImageUrl, setCaptureImageUrl] = useState<string | null>(null);
  const [startError, setStartError] = useState("");
  const [starting, setStarting] = useState(false);
  const sessionRef = useRef<TelemetrySession | null>(null);
  const brokerUrl = import.meta.env.VITE_MQTT_BROKER_URL;
  const deviceId = import.meta.env.VITE_DEVICE_ID ?? "station-01";
  useEffect(() => {
    if (!brokerUrl) return undefined;
    const session = subscribeToTelemetry(
      brokerUrl,
      deviceId,
      (message) => {
        if (message.stage === "MOUNTED") {
          setFailureTarget("exterior");
          setCaptureImageUrl(null);
        }
        if (message.captureImageUrl) setCaptureImageUrl(message.captureImageUrl);
        if (
          message.stage === "LED_CHECK" &&
          /PWR|LED|power/i.test(message.message) &&
          /off|fail|error|issue|unlit|not lit/i.test(message.message)
        )
          setFailureTarget("pwr-led");
        setTelemetry(message);
        setView(viewForTelemetry(message));
      },
      setConnection,
    );
    sessionRef.current = session;
    return () => {
      sessionRef.current = null;
      session.close();
    };
  }, [brokerUrl, deviceId]);
  const connected = connection === "connected";
  const startInspection = async () => {
    setStartError("");
    if (!brokerUrl) { setView("ocr"); return; }
    if (!connected || !sessionRef.current) {
      setStartError("Please check the connection and try again.");
      return;
    }
    setStarting(true);
    try {
      if (!await sessionRef.current.publishStart()) {
        setStartError("Failed to start inspection. Please try again.");
        return;
      }
      setView(current => (current === "ready" || current === "reposition") ? "ocr" : current);
    } catch {
      setStartError("Failed to start inspection. Please try again.");
    } finally {
      setStarting(false);
    }
  };
  const advance = () => {
    const next = nextView[view];
    if (next === "ready") {
      setCaptureImageUrl(null);
      setTelemetry(null);
      setStartError("");
    }
    setView(next);
  };
  const button = (label: string) => (
    <Button size="kiosk" className="absolute bottom-10 right-12" onClick={advance}>
      {label}
    </Button>
  );
  const content = (() => {
    switch (view) {
      case "ready":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title title="Ready to return your device?" subtitle="Place the board in the center and connect USB-C power." />
            <div className="absolute left-6 top-44 text-[13px] leading-8 text-secondary dark:text-slate-400">
              <p>• Connect the USB-C power cable.</p>
              <p>• Do not move the board during inspection.</p>
            </div>
            <div className="absolute left-[423px] top-[156px] w-[282px] text-center text-xs text-secondary dark:text-slate-400">
              <ReadyCameraPreview />
              <span className="mt-2 block">Center the board inside the guide.</span>
            </div>
            {startError && <p role="alert" className="absolute bottom-[104px] left-6 text-xs text-danger">{startError}</p>}
            <Button size="kiosk" className="absolute bottom-10 left-6" disabled={starting} onClick={() => void startInspection()}>
              Start Inspection
            </Button>
          </>
        );
      case "ocr":
      case "led":
      case "ai":
        return (
          <ProgressView
            view={view}
            telemetry={telemetry}
            captureImageUrl={captureImageUrl}
            connected={connected}
            connection={connection}
          />
        );
      case "pass":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title title="Inspection passed" subtitle="No issues found. You can complete your return." />
            <ResultChecks mode="pass" />
            {button("Complete Return")}
          </>
        );
      case "complete":
        return (
          <div className="absolute inset-0 flex flex-col items-center pt-14 text-center">
            <img src={completeImage} alt="Happy completion character" className="size-[150px] object-contain" />
            <h1 className="mt-6 text-3xl font-bold">Return complete!</h1>
            <p className="mt-2 text-[15px] text-secondary dark:text-slate-400">Your inspection record has been sent to the admin.</p>
            <div className="mt-5 grid h-[58px] w-[420px] grid-cols-[106px_1fr] items-center rounded-[14px] border border-line-soft px-4 text-left text-xs dark:border-[#334155]">
              <span className="text-secondary dark:text-slate-400">Inspection ID</span>
              <strong className="min-w-0 break-all">
                {telemetry?.inspectionId ?? "7b2c4d91-a6e8-4fd0-b53a-2c4e6f8a1b90"}
              </strong>
            </div>
            <small className="mt-3 text-xs text-muted">Returning to the start screen shortly.</small>
          </div>
        );
      case "reposition":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title
              title="Please reposition the board"
              subtitle={telemetry?.message ?? "Check the guidance and try the inspection again."}
            />
            <ResultChecks mode="reposition" />
            <span className="absolute left-11 top-[365px] text-xs font-medium text-amber-700">
              Retry&nbsp; {telemetry?.stage === "REPOSITION" ? telemetry.repositionCount : 1} / 3
            </span>
            <Button
              size="kiosk"
              className="absolute bottom-10 right-12"
              disabled={starting}
              onClick={() => {
                setCaptureImageUrl(null);
                setTelemetry(null);
                void startInspection();
              }}
            >
              Retry Inspection
            </Button>
          </>
        );
      case "fail":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title title="Potential issue detected" subtitle="An administrator will review the inspection result." />
            <ResultChecks mode="fail" failureTarget={failureTarget} />
            {button("Back to Start")}
          </>
        );
      case "manual":
      case "error":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title
              title="Please return to an administrator"
              subtitle="Automatic inspection could not be completed. Please hand the board to an administrator."
            />
            <img
              className="absolute left-[330px] top-[190px] size-36 object-contain"
              src={manualImage}
              alt="Concerned guide character"
            />
            {button("Back to Start")}
          </>
        );
      default:
        return assertNever(view);
    }
  })();
  return (
    <main className="grid min-h-[100dvh] place-items-center overflow-hidden bg-canvas dark:bg-[#0b1018]">
      <section className="relative h-[480px] w-[800px] shrink-0 overflow-hidden rounded-[22px] border border-line bg-white dark:border-[#273446] dark:bg-[#121a26]">
        {content}
        <div className="absolute left-6 top-4">
          <ThemeToggle compact />
        </div>
      </section>
    </main>
  );
}

function Header({ connected, connection }: { readonly connected: boolean; readonly connection: TelemetryConnection }) {
  const label = !import.meta.env.VITE_MQTT_BROKER_URL
    ? "Demo Mode"
    : connection === "connecting"
      ? "Connecting"
      : connected
        ? "Live"
        : connection === "error"
          ? "Connection Error"
          : "Disconnected";
  return <SystemStatus connected={connected} label={label} />;
}
function Title({ title, subtitle }: { readonly title: string; readonly subtitle: string }) {
  return (
    <>
      <h1 className="absolute left-6 top-[72px] w-[650px] text-[28px] font-bold tracking-tight">{title}</h1>
      <p className="absolute left-6 top-[118px] w-[650px] text-sm text-secondary dark:text-slate-400">{subtitle}</p>
    </>
  );
}
function ReadyCameraPreview() {
  return (
    <div className="relative h-[200px] w-[282px] overflow-hidden rounded-xl bg-slate-300">
      <CameraImage fallbackImageUrl={boardImage} fallbackAlt="Raspberry Pi board centered on inspection station" className="object-cover" />
      <span
        role="img"
        aria-label="Board placement guide"
        className="pointer-events-none absolute inset-7 rounded-lg border-3 border-primary/70"
      />
    </div>
  );
}
function getCandidateFeeds(): string[] {
  return (import.meta.env.VITE_CAMERA_FEED_URL ?? "")
    .split(",")
    .map((url: string) => url.trim())
    .filter(Boolean);
}

function CameraImage({
  imageUrl,
  fallbackImageUrl,
  fallbackAlt,
  className,
}: {
  readonly imageUrl?: string | null;
  readonly fallbackImageUrl: string;
  readonly fallbackAlt: string;
  readonly className: string;
}) {
  const [feedIndex, setFeedIndex] = useState(0);
  const [allFailed, setAllFailed] = useState(false);

  const candidateFeeds = getCandidateFeeds();
  const currentFeed = candidateFeeds[feedIndex];

  const handleError = () => {
    if (feedIndex + 1 < candidateFeeds.length) {
      setFeedIndex((prev) => prev + 1);
    } else {
      setAllFailed(true);
    }
  };

  if (allFailed || !currentFeed) {
    if (imageUrl) {
      return (
        <img
          src={imageUrl}
          alt={fallbackAlt}
          className={`h-full w-full ${className}`}
        />
      );
    }
    return (
      <>
        <img
          src={fallbackImageUrl}
          alt={fallbackAlt}
          className={`h-full w-full ${className}`}
        />
        <span className="absolute bottom-1 left-1 rounded bg-slate-900/75 px-1.5 py-0.5 text-[10px] text-white">
          Camera disconnected
        </span>
      </>
    );
  }

  return (
    <img
      key={currentFeed}
      src={currentFeed}
      alt="Live camera preview"
      onError={handleError}
      className={`h-full w-full ${className}`}
    />
  );
}
function ProgressCameraPreview({ captureImageUrl }: { readonly captureImageUrl: string | null }) {
  return (
    <div className="absolute left-6 top-[174px] h-[186px] w-[370px] overflow-hidden rounded-2xl border border-line-soft bg-slate-50 p-4 dark:border-[#334155] dark:bg-[#182231]">
      <div className="relative h-full w-full overflow-hidden rounded-lg">
        <CameraImage
          imageUrl={captureImageUrl}
          fallbackImageUrl={boardImage}
          fallbackAlt={captureImageUrl ? "Raspberry Pi board captured at station" : "Raspberry Pi board centered on inspection station"}
          className="object-contain"
        />
      </div>
    </div>
  );
}
function ProgressView({
  view,
  telemetry,
  captureImageUrl,
  connected,
  connection,
}: {
  readonly view: "ocr" | "led" | "ai";
  readonly telemetry: Telemetry | null;
  readonly captureImageUrl: string | null;
  readonly connected: boolean;
  readonly connection: TelemetryConnection;
}) {
  const config = {
    ocr: {
      accent: "Serial ID",
      fallback: "Recognizing the unique serial number via camera",
      progress: 20,
      rows: ["active", "muted", "muted"],
    },
    led: {
      accent: "Power LED",
      fallback: "Serial ID verified. Checking the power indicator LED.",
      progress: 58,
      rows: ["success", "active", "muted"],
    },
    ai: {
      accent: "Exterior",
      fallback: "Almost done. Inspecting the board exterior.",
      progress: 86,
      rows: ["success", "success", "active"],
    },
  } as const;
  const current = config[view];
  return (
    <>
      <Header connected={connected} connection={connection} />
      <h1 className="absolute left-6 top-[72px] text-[28px] font-bold">
        Checking board <em className="not-italic text-primary">{current.accent}</em>
      </h1>
      <p className="absolute left-6 top-[118px] text-sm text-secondary dark:text-slate-400">
        {telemetry?.message ?? current.fallback}
      </p>
      <ProgressCameraPreview captureImageUrl={captureImageUrl} />
      <div className="absolute left-[423px] top-[174px] grid w-80 gap-5">
        {["Serial Verification", "Power LED", "Exterior Inspection"].map((label, index) => {
          const tone = current.rows[index] ?? "muted";
          return (
            <InspectionCheck
              key={label}
              label={label}
              state={tone === "success" ? "Done" : tone === "active" ? "In Progress" : "Pending"}
              tone={tone}
            />
          );
        })}
      </div>
      <ProgressBar
        value={telemetry?.progressPercent ?? current.progress}
        label={telemetry ? `${telemetry.progressPercent}%` : import.meta.env.VITE_MQTT_BROKER_URL ? "Waiting" : "Demo"}
      />
    </>
  );
}
function ResultChecks({
  mode,
  failureTarget = "exterior",
}: {
  readonly mode: "pass" | "reposition" | "fail";
  readonly failureTarget?: FailureTarget;
}) {
  const stacked = mode !== "pass";
  const pwrFailed = mode === "fail" && failureTarget === "pwr-led";
  const exteriorFailed = mode === "fail" && failureTarget === "exterior";
  return (
    <div
      className={`absolute top-[174px] grid h-44 w-[728px] rounded-2xl border border-line-soft bg-slate-50 p-4 dark:border-[#334155] dark:bg-[#182231] ${stacked ? "left-9 grid-cols-1 gap-2" : "left-6 grid-cols-2 gap-x-12 gap-y-5"}`}
    >
      <InspectionCheck
        compact={stacked}
        label="PWR LED Status"
        state={mode === "pass" ? "Normal" : pwrFailed ? "Needs Check" : mode === "fail" ? "Normal" : "N/A"}
        tone={mode === "pass" ? "success" : pwrFailed ? "warning" : "muted"}
      />
      <InspectionCheck
        compact={stacked}
        label="Exterior Inspection"
        state={mode === "pass" ? "Normal" : exteriorFailed ? "Needs Check" : mode === "fail" ? "Normal" : "N/A"}
        tone={mode === "pass" ? "success" : exteriorFailed ? "warning" : "muted"}
      />
      <InspectionCheck
        compact={stacked}
        label="Serial Recognition"
        state={
          mode === "reposition" ? "Needs Check" : mode === "pass" ? "Normal" : mode === "fail" ? "Recognized" : "N/A"
        }
        tone={mode === "reposition" ? "warning" : mode === "pass" ? "success" : "muted"}
      />
    </div>
  );
}
