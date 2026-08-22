import { useEffect, useRef, useState } from 'react';

const palette = {
  void: '#050505',
  night: '#090909',
  carbon: '#111111',
  charcoal: '#1d1d1d',
  graphite: '#555555',
  mist: '#8a8a86',
  fog: '#b9b9b4',
  paper: '#f4f4ef',
} as const;

interface SceneMetrics {
  width: number;
  height: number;
  horizon: number;
}

function modulo(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}

function hash(value: number): number {
  const x = Math.sin(value * 91.3458 + 17.123) * 47453.5453;
  return x - Math.floor(x);
}

function drawStars(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  time: number,
  reducedMotion: boolean,
) {
  const starCount = Math.max(34, Math.floor(metrics.width / 7));

  for (let index = 0; index < starCount; index += 1) {
    const x = Math.floor(hash(index * 4.17) * metrics.width);
    const y = Math.floor(4 + hash(index * 8.73) * metrics.horizon * 0.68);
    const pulse = reducedMotion
      ? hash(index * 2.91)
      : (Math.sin(time * (0.55 + hash(index) * 0.9) + index) + 1) / 2;

    context.fillStyle = pulse > 0.72 ? palette.paper : palette.graphite;
    context.fillRect(x, y, pulse > 0.93 ? 2 : 1, 1);

    if (index % 19 === 4 && pulse > 0.78) {
      context.fillRect(x, y - 2, 1, 5);
      context.fillRect(x - 2, y, 5, 1);
      context.fillStyle = palette.void;
      context.fillRect(x, y, 1, 1);
    }
  }
}

function drawDitheredCloud(
  context: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  scale: number,
  seed: number,
  tone: string,
) {
  const pixel = Math.max(1, Math.round(scale));
  const blocks = [
    [-18, 1, 36, 4],
    [-13, -3, 26, 6],
    [-8, -7, 17, 7],
    [-2, -11, 10, 8],
    [8, -5, 13, 8],
    [-23, 4, 49, 3],
  ] as const;

  context.fillStyle = tone;
  for (const [x, y, width, height] of blocks) {
    context.fillRect(
      Math.round(centerX + x * scale),
      Math.round(centerY + y * scale),
      Math.ceil(width * scale),
      Math.ceil(height * scale),
    );
  }

  const minX = Math.floor(centerX - 24 * scale);
  const maxX = Math.ceil(centerX + 26 * scale);
  const minY = Math.floor(centerY - 12 * scale);
  const maxY = Math.ceil(centerY + 9 * scale);

  for (let y = minY; y < maxY; y += pixel) {
    for (let x = minX; x < maxX; x += pixel) {
      const noise = hash(x * 0.71 + y * 1.91 + seed * 13.7);

      if (noise > 0.77) {
        context.fillStyle = noise > 0.91 ? palette.fog : palette.void;
        context.fillRect(x, y, pixel, pixel);
      }
    }
  }

  context.fillStyle = palette.graphite;
  context.fillRect(
    Math.round(centerX - 19 * scale),
    Math.round(centerY + 7 * scale),
    Math.round(39 * scale),
    pixel,
  );
}

function drawCloudLayers(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  time: number,
  reducedMotion: boolean,
) {
  const clouds = [
    { position: 0.06, y: 0.27, scale: 0.72, speed: 0.75, seed: 3, tone: palette.charcoal },
    { position: 0.34, y: 0.18, scale: 1.12, speed: 1.05, seed: 7, tone: palette.graphite },
    { position: 0.69, y: 0.32, scale: 0.58, speed: 0.62, seed: 11, tone: palette.charcoal },
    { position: 0.91, y: 0.22, scale: 0.84, speed: 0.88, seed: 17, tone: palette.graphite },
  ] as const;

  for (const cloud of clouds) {
    const travel = reducedMotion ? 0 : time * cloud.speed;
    const paddedWidth = metrics.width + 92;
    const x = modulo(cloud.position * metrics.width - travel + 46, paddedWidth) - 46;
    drawDitheredCloud(
      context,
      x,
      metrics.height * cloud.y,
      cloud.scale,
      cloud.seed,
      cloud.tone,
    );
  }
}

function drawPlane(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  time: number,
  reducedMotion: boolean,
) {
  const activeDuration = 11;
  const cycleDuration = 31;
  const cycleTime = modulo(time + 4.2, cycleDuration);
  const visible = reducedMotion || cycleTime < activeDuration;

  if (!visible) {
    return;
  }

  const progress = reducedMotion ? 0.67 : cycleTime / activeDuration;
  const x = Math.round(-24 + progress * (metrics.width + 48));
  const arc = Math.sin(progress * Math.PI);
  const y = Math.round(metrics.height * 0.29 - arc * metrics.height * 0.14);

  context.fillStyle = palette.graphite;
  for (let dot = 2; dot < 22; dot += 3) {
    const trailX = x - dot * 3;
    const trailY = Math.round(y + dot * 0.55 + Math.sin(dot * 0.7) * 2);
    context.fillRect(trailX, trailY, 1, 1);
  }

  context.save();
  context.translate(x, y);
  context.fillStyle = palette.paper;
  context.fillRect(-8, 0, 18, 2);
  context.fillRect(1, -5, 3, 11);
  context.fillRect(-2, -3, 3, 7);
  context.fillRect(7, -2, 2, 6);
  context.fillRect(-9, -1, 3, 1);
  context.fillStyle = palette.graphite;
  context.fillRect(4, 0, 2, 1);
  context.restore();
}

function drawControlTower(
  context: CanvasRenderingContext2D,
  x: number,
  baseline: number,
  height: number,
) {
  context.fillStyle = palette.charcoal;
  context.fillRect(x + 4, baseline - height + 8, 5, height - 8);
  context.fillStyle = palette.graphite;
  context.fillRect(x + 2, baseline - height + 4, 9, 4);
  context.fillRect(x, baseline - height + 6, 13, 2);
  context.fillStyle = palette.fog;
  context.fillRect(x + 3, baseline - height + 5, 2, 1);
  context.fillRect(x + 7, baseline - height + 5, 2, 1);
  context.fillRect(x + 6, baseline - height, 1, 4);
}

function drawFarSkyline(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  worldOffset: number,
) {
  const baseline = metrics.horizon - 8;
  const segmentWidth = 11;
  const parallax = worldOffset * 0.18;
  const startIndex = Math.floor(parallax / segmentWidth) - 2;
  const endIndex = startIndex + Math.ceil(metrics.width / segmentWidth) + 5;

  for (let worldIndex = startIndex; worldIndex < endIndex; worldIndex += 1) {
    const x = Math.floor(worldIndex * segmentWidth - parallax);
    const towerPosition = modulo(worldIndex, 41);

    if (towerPosition === 19) {
      drawControlTower(context, x, baseline, 31);
      continue;
    }

    const buildingHeight = 5 + Math.floor(hash(worldIndex * 2.07) * 17);
    const buildingWidth = 7 + Math.floor(hash(worldIndex * 4.11) * 7);
    context.fillStyle = palette.charcoal;
    context.fillRect(x, baseline - buildingHeight, buildingWidth, buildingHeight);

    if (buildingHeight > 9) {
      context.fillStyle = hash(worldIndex) > 0.55 ? palette.graphite : palette.night;
      for (let windowY = baseline - buildingHeight + 3; windowY < baseline - 2; windowY += 4) {
        context.fillRect(x + 2, windowY, 1, 1);
        if (buildingWidth > 10) {
          context.fillRect(x + 6, windowY, 1, 1);
        }
      }
    }
  }
}

function drawTerminalLayer(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  worldOffset: number,
) {
  const roofY = metrics.horizon - 5;
  const parallax = worldOffset * 0.42;

  context.fillStyle = palette.night;
  context.fillRect(0, roofY, metrics.width, 13);
  context.fillStyle = palette.graphite;
  context.fillRect(0, roofY, metrics.width, 1);

  for (let index = -2; index < Math.ceil(metrics.width / 18) + 3; index += 1) {
    const x = Math.floor(index * 18 - modulo(parallax, 18));
    const worldIndex = Math.floor(parallax / 18) + index;
    const roofLift = hash(worldIndex * 7.3) > 0.72 ? 4 : 0;

    context.fillStyle = palette.charcoal;
    context.fillRect(x, roofY - roofLift, 15, 4 + roofLift);
    context.fillStyle = hash(worldIndex * 3.17) > 0.44 ? palette.fog : palette.graphite;
    context.fillRect(x + 3, roofY + 4, 2, 1);
    context.fillRect(x + 9, roofY + 4, 2, 1);
  }

  for (let index = -1; index < Math.ceil(metrics.width / 31) + 2; index += 1) {
    const x = Math.floor(index * 31 - modulo(worldOffset * 0.58, 31));
    const poleHeight = 11 + Math.floor(hash(index + Math.floor(worldOffset / 31)) * 5);
    context.fillStyle = palette.graphite;
    context.fillRect(x, roofY - poleHeight, 1, poleHeight);
    context.fillStyle = palette.paper;
    context.fillRect(x - 2, roofY - poleHeight, 5, 1);
    context.fillRect(x, roofY - poleHeight - 1, 1, 3);
  }
}

function drawGround(
  context: CanvasRenderingContext2D,
  metrics: SceneMetrics,
  worldOffset: number,
) {
  const groundY = metrics.horizon + 7;
  context.fillStyle = palette.night;
  context.fillRect(0, groundY, metrics.width, metrics.height - groundY);
  context.fillStyle = palette.paper;
  context.fillRect(0, groundY, metrics.width, 1);
  context.fillStyle = palette.graphite;
  context.fillRect(0, groundY + 3, metrics.width, 1);

  const markerOffset = modulo(worldOffset * 1.35, 24);
  for (let x = -24; x < metrics.width + 24; x += 24) {
    context.fillStyle = palette.fog;
    context.fillRect(Math.floor(x - markerOffset), groundY + 8, 9, 1);
  }

  const fleckCount = Math.floor(metrics.width * 0.72);
  for (let index = 0; index < fleckCount; index += 1) {
    const worldX = index * 5 + Math.floor(worldOffset * 1.8);
    const x = modulo(index * 7 - worldOffset * 1.8, metrics.width);
    const depth = hash(worldX * 0.37);
    const y = Math.floor(groundY + 12 + depth * Math.max(1, metrics.height - groundY - 13));

    if (hash(worldX * 1.71) > 0.55) {
      context.fillStyle = depth > 0.68 ? palette.graphite : palette.charcoal;
      context.fillRect(Math.floor(x), y, depth > 0.82 ? 2 : 1, 1);
    }
  }
}

function drawTraveler(
  context: CanvasRenderingContext2D,
  x: number,
  footY: number,
  time: number,
  reducedMotion: boolean,
) {
  const gait = reducedMotion ? 1 : Math.sin(time * 8.2) >= 0 ? 1 : -1;
  const bob = reducedMotion ? 0 : Math.round((Math.sin(time * 16.4) + 1) * 0.5);

  context.save();
  context.translate(Math.round(x), Math.round(footY + bob));

  context.fillStyle = palette.graphite;
  context.fillRect(-8, -19, 5, 11);
  context.fillStyle = palette.fog;
  context.fillRect(-7, -17, 1, 7);
  context.fillRect(-5, -20, 3, 2);

  context.fillStyle = palette.paper;
  context.fillRect(-2, -29, 8, 7);
  context.fillStyle = palette.graphite;
  context.fillRect(-3, -30, 8, 2);
  context.fillRect(4, -29, 4, 2);
  context.fillStyle = palette.void;
  context.fillRect(4, -26, 1, 1);

  context.fillStyle = palette.fog;
  context.fillRect(0, -22, 3, 3);
  context.fillStyle = palette.paper;
  context.fillRect(-2, -20, 10, 11);
  context.fillStyle = palette.graphite;
  context.fillRect(0, -18, 6, 7);
  context.fillStyle = palette.void;
  context.fillRect(2, -16, 2, 3);
  context.fillStyle = palette.fog;
  context.fillRect(-3, -19, 2, 8);

  context.fillStyle = palette.paper;
  context.fillRect(7, -18 + gait, 3, 8);
  context.fillRect(9, -11 + gait, 4, 2);
  context.fillStyle = palette.graphite;
  context.fillRect(-4, -16 - gait, 2, 7);

  context.fillStyle = palette.paper;
  context.fillRect(-1 + gait, -9, 4, 8);
  context.fillRect(5 - gait, -9, 4, 8);
  context.fillStyle = palette.graphite;
  context.fillRect(-2 + gait, -2, 6, 2);
  context.fillRect(4 - gait, -2, 7, 2);

  context.fillStyle = palette.graphite;
  context.fillRect(-9, -12, 2, 1);
  context.fillRect(-11, -13, 2, 1);

  context.restore();
}

function drawScene(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
  reducedMotion: boolean,
) {
  const horizonRatio = width < 320 ? 0.56 : 0.66;
  const metrics: SceneMetrics = {
    width,
    height,
    horizon: Math.round(height * horizonRatio),
  };
  const worldOffset = reducedMotion ? 34 : time * 8.2;

  context.clearRect(0, 0, width, height);
  context.fillStyle = palette.void;
  context.fillRect(0, 0, width, height);

  drawStars(context, metrics, time, reducedMotion);
  drawCloudLayers(context, metrics, time, reducedMotion);
  drawPlane(context, metrics, time, reducedMotion);
  drawFarSkyline(context, metrics, worldOffset);
  drawTerminalLayer(context, metrics, worldOffset);
  drawGround(context, metrics, worldOffset);

  const travelerX = width < 320 ? width * 0.24 : width * 0.29;
  drawTraveler(
    context,
    travelerX,
    metrics.horizon + 7,
    time,
    reducedMotion,
  );
}

export function PixelJourneyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pauseRef = useRef(false);
  const restartAnimationRef = useRef<() => void>(() => undefined);
  const [isPaused, setIsPaused] = useState(false);

  function toggleScenery() {
    const nextPaused = !pauseRef.current;
    pauseRef.current = nextPaused;
    setIsPaused(nextPaused);

    if (!nextPaused) {
      restartAnimationRef.current();
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current;

    if (!canvas) {
      return;
    }

    const context = canvas.getContext('2d', { alpha: false });

    if (!context) {
      return;
    }

    const sceneCanvas = canvas;
    const sceneContext = context;

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reducedMotion = motionQuery.matches;
    let animationFrame = 0;
    let elapsed = 0;
    let lastFrame = performance.now();

    function renderFrame(now: number) {
      if (pauseRef.current) {
        return;
      }

      const delta = Math.min(0.05, Math.max(0, (now - lastFrame) / 1000));
      lastFrame = now;
      elapsed += delta;
      drawScene(
        sceneContext,
        sceneCanvas.width,
        sceneCanvas.height,
        elapsed,
        reducedMotion,
      );

      if (
        !reducedMotion &&
        !pauseRef.current &&
        document.visibilityState === 'visible'
      ) {
        animationFrame = window.requestAnimationFrame(renderFrame);
      }
    }

    function drawStaticFrame() {
      drawScene(sceneContext, sceneCanvas.width, sceneCanvas.height, 6.4, true);
    }

    function startAnimation() {
      window.cancelAnimationFrame(animationFrame);

      if (pauseRef.current) {
        return;
      }

      if (reducedMotion || document.visibilityState !== 'visible') {
        drawStaticFrame();
        return;
      }

      lastFrame = performance.now();
      animationFrame = window.requestAnimationFrame(renderFrame);
    }

    function resizeCanvas() {
      const bounds = sceneCanvas.getBoundingClientRect();
      const pixelSize = bounds.width < 720 ? 2 : 3;
      const nextWidth = Math.max(1, Math.ceil(bounds.width / pixelSize));
      const nextHeight = Math.max(1, Math.ceil(bounds.height / pixelSize));

      if (sceneCanvas.width !== nextWidth || sceneCanvas.height !== nextHeight) {
        sceneCanvas.width = nextWidth;
        sceneCanvas.height = nextHeight;
        sceneContext.imageSmoothingEnabled = false;
      }

      if (reducedMotion) {
        drawStaticFrame();
      } else if (pauseRef.current) {
        drawScene(
          sceneContext,
          sceneCanvas.width,
          sceneCanvas.height,
          elapsed,
          false,
        );
      }
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'hidden') {
        window.cancelAnimationFrame(animationFrame);
        return;
      }

      startAnimation();
    }

    function handleMotionPreference(event: MediaQueryListEvent) {
      reducedMotion = event.matches;
      startAnimation();
    }

    restartAnimationRef.current = startAnimation;

    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(sceneCanvas);
    motionQuery.addEventListener('change', handleMotionPreference);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    resizeCanvas();
    startAnimation();

    return () => {
      restartAnimationRef.current = () => undefined;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      motionQuery.removeEventListener('change', handleMotionPreference);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="pixel-journey"
        aria-hidden="true"
      />
      <button
        className="scene-motion-control"
        type="button"
        data-paused={isPaused}
        onClick={toggleScenery}
      >
        <span className="scene-motion-control__icon" aria-hidden="true" />
        <span>{isPaused ? 'Play scenery' : 'Pause scenery'}</span>
      </button>
    </>
  );
}

