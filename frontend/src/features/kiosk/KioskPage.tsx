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
          /PWR|LED|전원/i.test(message.message) &&
          /꺼|불량|실패|문제|켜지지/i.test(message.message)
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
      setStartError("연결을 확인한 뒤 다시 시도해 주세요.");
      return;
    }
    setStarting(true);
    try {
      if (!await sessionRef.current.publishStart()) {
        setStartError("검사를 시작하지 못했습니다. 다시 시도해 주세요.");
        return;
      }
      setView(current => (current === "ready" || current === "reposition") ? "ocr" : current);
    } catch {
      setStartError("검사를 시작하지 못했습니다. 다시 시도해 주세요.");
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
            <Title title="반납을 시작할까요?" subtitle="보드를 정가운데에 놓고 USB-C 전원을 연결해주세요." />
            <div className="absolute left-6 top-44 text-[13px] leading-8 text-secondary dark:text-slate-400">
              <p>• USB-C 전원을 연결해 주세요.</p>
              <p>• 검사 중에는 보드를 움직이지 말아 주세요.</p>
            </div>
            <div className="absolute left-[423px] top-[156px] w-[282px] text-center text-xs text-secondary dark:text-slate-400">
              <ReadyCameraPreview />
              <span className="mt-2 block">보드를 정가운데에 놓아주세요.</span>
            </div>
            {startError && <p role="alert" className="absolute bottom-[104px] left-6 text-xs text-danger">{startError}</p>}
            <Button size="kiosk" className="absolute bottom-10 left-6" disabled={starting} onClick={() => void startInspection()}>
              검사 시작
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
            <Title title="검사가 정상적으로 완료됐어요" subtitle="이상이 없어요. 이제 반납할 수 있어요." />
            <ResultChecks mode="pass" />
            {button("반납 완료")}
          </>
        );
      case "complete":
        return (
          <div className="absolute inset-0 flex flex-col items-center pt-14 text-center">
            <img src={completeImage} alt="기쁜 표정의 완료 캐릭터" className="size-[150px] object-contain" />
            <h1 className="mt-6 text-3xl font-bold">반납이 완료됐어요!</h1>
            <p className="mt-2 text-[15px] text-secondary dark:text-slate-400">검사 이력은 관리자에게 전달돼요.</p>
            <div className="mt-5 grid h-[58px] w-[420px] grid-cols-[106px_1fr] items-center rounded-[14px] border border-line-soft px-4 text-left text-xs dark:border-[#334155]">
              <span className="text-secondary dark:text-slate-400">검사 ID</span>
              <strong className="min-w-0 break-all">
                {telemetry?.inspectionId ?? "7b2c4d91-a6e8-4fd0-b53a-2c4e6f8a1b90"}
              </strong>
            </div>
            <small className="mt-3 text-xs text-muted">잠시 후 첫 화면으로 돌아갑니다.</small>
          </div>
        );
      case "reposition":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title
              title="보드를 다시 놓아주세요"
              subtitle={telemetry?.message ?? "안내된 항목을 확인한 뒤 다시 검사해 주세요."}
            />
            <ResultChecks mode="reposition" />
            <span className="absolute left-11 top-[365px] text-xs font-medium text-amber-700">
              재시도 횟수&nbsp; {telemetry?.stage === "REPOSITION" ? telemetry.repositionCount : 1} / 3
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
              다시 검사
            </Button>
          </>
        );
      case "fail":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title title="보드에 문제가 의심돼요" subtitle="관리자가 검사 결과를 확인할 예정이에요." />
            <ResultChecks mode="fail" failureTarget={failureTarget} />
            {button("처음 화면으로")}
          </>
        );
      case "manual":
      case "error":
        return (
          <>
            <Header connected={connected} connection={connection} />
            <Title
              title="관리자에게 직접 반납해 주세요"
              subtitle="자동 검사를 완료하지 못했어요. 관리자에게 보드를 전달해 주세요."
            />
            <img
              className="absolute left-[330px] top-[190px] size-36 object-contain"
              src={manualImage}
              alt="걱정하는 표정의 안내 캐릭터"
            />
            {button("처음 화면으로")}
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
    ? "데모 모드"
    : connection === "connecting"
      ? "연결 중"
      : connected
        ? "실시간 연결"
        : connection === "error"
          ? "연결 오류"
          : "연결 끊김";
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
      <CameraImage fallbackImageUrl={boardImage} fallbackAlt="검사대 중앙에 놓인 Raspberry Pi 보드" className="object-cover" />
      <span
        role="img"
        aria-label="보드 배치 가이드"
        className="pointer-events-none absolute inset-7 rounded-lg border-3 border-primary/70"
      />
    </div>
  );
}
const CANDIDATE_FEEDS = (import.meta.env.VITE_CAMERA_FEED_URL ?? "")
  .split(",")
  .map((url: string) => url.trim())
  .filter(Boolean);

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

  // 캡처 이미지가 있으면 캡처 이미지 우선 사용
  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={fallbackAlt}
        className={`h-full w-full ${className}`}
      />
    );
  }

  const currentFeed = CANDIDATE_FEEDS[feedIndex];

  const handleError = () => {
    if (feedIndex + 1 < CANDIDATE_FEEDS.length) {
      setFeedIndex((prev) => prev + 1);
    } else {
      setAllFailed(true);
    }
  };

  if (allFailed || !currentFeed) {
    return (
      <>
        <img
          src={fallbackImageUrl}
          alt={fallbackAlt}
          className={`h-full w-full ${className}`}
        />
        <span className="absolute bottom-1 left-1 rounded bg-slate-900/75 px-1.5 py-0.5 text-[10px] text-white">
          카메라 연결 안 됨
        </span>
      </>
    );
  }

  return (
    <img
      key={currentFeed}
      src={currentFeed}
      alt="실시간 카메라 프리뷰"
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
          fallbackAlt={captureImageUrl ? "검사대에서 촬영한 Raspberry Pi 보드" : "검사대 중앙에 놓인 Raspberry Pi 보드"}
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
      accent: "고유번호",
      fallback: "카메라로 고유번호를 인식 중입니다",
      progress: 20,
      rows: ["active", "muted", "muted"],
    },
    led: {
      accent: "상태",
      fallback: "고유번호를 확인했어요. 전원 표시등을 검사 중이에요.",
      progress: 58,
      rows: ["success", "active", "muted"],
    },
    ai: {
      accent: "외관",
      fallback: "이제 거의 끝나가요. 외관을 검사 중이에요.",
      progress: 86,
      rows: ["success", "success", "active"],
    },
  } as const;
  const current = config[view];
  return (
    <>
      <Header connected={connected} connection={connection} />
      <h1 className="absolute left-6 top-[72px] text-[28px] font-bold">
        보드 <em className="not-italic text-primary">{current.accent}</em>를 확인하고 있어요
      </h1>
      <p className="absolute left-6 top-[118px] text-sm text-secondary dark:text-slate-400">
        {telemetry?.message ?? current.fallback}
      </p>
      <ProgressCameraPreview captureImageUrl={captureImageUrl} />
      <div className="absolute left-[423px] top-[174px] grid w-80 gap-5">
        {["고유번호 확인", "전원 표시등", "외관 검사"].map((label, index) => {
          const tone = current.rows[index] ?? "muted";
          return (
            <InspectionCheck
              key={label}
              label={label}
              state={tone === "success" ? "완료" : tone === "active" ? "진행 중" : "대기"}
              tone={tone}
            />
          );
        })}
      </div>
      <ProgressBar
        value={telemetry?.progressPercent ?? current.progress}
        label={telemetry ? `${telemetry.progressPercent}%` : import.meta.env.VITE_MQTT_BROKER_URL ? "대기" : "데모"}
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
        label="PWR LED 점등"
        state={mode === "pass" ? "정상" : pwrFailed ? "확인 필요" : mode === "fail" ? "이상 없음" : "해당 없음"}
        tone={mode === "pass" ? "success" : pwrFailed ? "warning" : "muted"}
      />
      <InspectionCheck
        compact={stacked}
        label="외관 검사"
        state={mode === "pass" ? "정상" : exteriorFailed ? "확인 필요" : mode === "fail" ? "이상 없음" : "해당 없음"}
        tone={mode === "pass" ? "success" : exteriorFailed ? "warning" : "muted"}
      />
      <InspectionCheck
        compact={stacked}
        label="고유번호 인식"
        state={
          mode === "reposition" ? "확인 필요" : mode === "pass" ? "정상" : mode === "fail" ? "인식 완료" : "해당 없음"
        }
        tone={mode === "reposition" ? "warning" : mode === "pass" ? "success" : "muted"}
      />
    </div>
  );
}
