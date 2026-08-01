/**
 * Scrolling live waveform — amplitude against time, drawn as a line on a grid.
 *
 * The visual reference is a plain matplotlib line plot: one thin stroke, a
 * light grid, a symmetric y axis around zero. Deliberately NOT the audio-editor
 * "filled blob" style, which is what you get from min/max peak-picking over a
 * long window; at this time scale individual cycles are visible, which is what
 * makes the difference between the raw and cleaned traces legible.
 *
 * Fed imperatively through the ref, same as LiveSpectrogram, so a burst of
 * audio callbacks does not cause a React render per block. A requestAnimationFrame
 * loop throttles redraws to the display refresh rate.
 */
import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Canvas, Path, Line, Skia, vec } from '@shopify/react-native-skia';

export type LiveWaveformHandle = {
  /** Append samples in [-1, 1]. Older samples fall off the left edge. */
  push: (samples: Float32Array) => void;
  clear: () => void;
};

type Props = {
  width: number;
  height: number;
  /** Rate of the incoming samples — sets how much time fits on screen. */
  sampleRate: number;
  /** Visible time span. ~80 ms shows a handful of snore cycles, like the reference. */
  windowMs?: number;
  /** Full-scale of the y axis. 0.5 matches a typical recording's peak. */
  yRange?: number;
  label?: string;
  color?: string;
  style?: object;
};

const GRID = 'rgba(255,255,255,0.10)';
const AXIS = 'rgba(255,255,255,0.22)';

export const LiveWaveform = forwardRef<LiveWaveformHandle, Props>(
  ({ width, height, sampleRate, windowMs = 80, yRange = 0.5,
     label, color = '#4C9BE8', style }, ref) => {

    const capacity = Math.max(64, Math.round((sampleRate * windowMs) / 1000));
    // Ring buffer of the most recent `capacity` samples.
    const ringRef = useRef(new Float32Array(capacity));
    const writeRef = useRef(0);
    const filledRef = useRef(0);
    const dirtyRef = useRef(false);
    const [path, setPath] = useState(() => Skia.Path.Make());

    useEffect(() => {
      ringRef.current = new Float32Array(capacity);
      writeRef.current = 0;
      filledRef.current = 0;
      dirtyRef.current = true;
    }, [capacity]);

    useImperativeHandle(ref, () => ({
      push: (samples: Float32Array) => {
        if (!samples.length) return;
        const ring = ringRef.current;
        const cap = ring.length;
        // Only the last `cap` samples can possibly remain visible.
        const start = samples.length > cap ? samples.length - cap : 0;
        let w = writeRef.current;
        for (let i = start; i < samples.length; i++) {
          ring[w] = samples[i];
          w = w + 1 === cap ? 0 : w + 1;
        }
        writeRef.current = w;
        filledRef.current = Math.min(cap, filledRef.current + (samples.length - start));
        dirtyRef.current = true;
      },
      clear: () => {
        ringRef.current.fill(0);
        writeRef.current = 0;
        filledRef.current = 0;
        dirtyRef.current = true;
      },
    }), []);

    // Rebuild the stroke at most once per frame.
    useEffect(() => {
      let raf = 0;
      let alive = true;
      const loop = () => {
        if (!alive) return;
        if (dirtyRef.current) {
          dirtyRef.current = false;
          setPath(buildPath(ringRef.current, writeRef.current, filledRef.current,
                            width, height, yRange));
        }
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
      return () => { alive = false; cancelAnimationFrame(raf); };
    }, [width, height, yRange]);

    // Horizontal grid lines at the quarter marks, plus a brighter zero axis.
    const gridYs = useMemo(() => {
      const fracs = [0, 0.25, 0.5, 0.75, 1];
      return fracs.map(f => ({ y: f * height, isZero: Math.abs(f - 0.5) < 1e-6 }));
    }, [height]);
    const gridXs = useMemo(
      () => [0.2, 0.4, 0.6, 0.8].map(f => f * width), [width]);

    return (
      <View style={[styles.wrap, style]}>
        {label ? <Text style={styles.label}>{label}</Text> : null}
        <View style={{ width, height }}>
          <Canvas style={{ width, height }}>
            {gridXs.map((x, i) => (
              <Line key={`vx${i}`} p1={vec(x, 0)} p2={vec(x, height)}
                    color={GRID} strokeWidth={1} />
            ))}
            {gridYs.map(({ y, isZero }, i) => (
              <Line key={`hz${i}`} p1={vec(0, y)} p2={vec(width, y)}
                    color={isZero ? AXIS : GRID} strokeWidth={1} />
            ))}
            <Path path={path} style="stroke" strokeWidth={1.6} color={color}
                  strokeJoin="round" strokeCap="round" />
          </Canvas>
          <Text style={[styles.tick, { top: -2 }]}>{`+${yRange}`}</Text>
          <Text style={[styles.tick, { bottom: -2 }]}>{`-${yRange}`}</Text>
        </View>
      </View>
    );
  },
);

/**
 * Ring buffer → Skia path.
 *
 * There are far more samples than horizontal pixels (80 ms at 16 kHz is 1280
 * samples across ~350 px), so plotting every sample would waste most of the
 * work. One point per pixel column, taking the extreme value in that column so
 * a peak between samples is never skipped and the trace keeps its true height.
 */
function buildPath(ring: Float32Array, write: number, filled: number,
                   width: number, height: number, yRange: number) {
  const p = Skia.Path.Make();
  if (filled < 2) return p;

  const cap = ring.length;
  const oldest = (write - filled + cap) % cap;
  const mid = height / 2;
  const scale = mid / yRange;
  const cols = Math.max(2, Math.min(width, filled));
  const per = filled / cols;

  for (let c = 0; c < cols; c++) {
    const from = Math.floor(c * per);
    const to = Math.min(filled, Math.floor((c + 1) * per));
    let extreme = 0;
    for (let i = from; i < to; i++) {
      const v = ring[(oldest + i) % cap];
      if (Math.abs(v) > Math.abs(extreme)) extreme = v;
    }
    const x = (c / (cols - 1)) * width;
    // Screen y grows downward, so a positive amplitude moves up.
    let y = mid - extreme * scale;
    if (y < 0) y = 0; else if (y > height) y = height;
    if (c === 0) p.moveTo(x, y); else p.lineTo(x, y);
  }
  return p;
}

LiveWaveform.displayName = 'LiveWaveform';

const styles = StyleSheet.create({
  wrap: { marginBottom: 10 },
  label: { color: 'rgba(255,255,255,0.75)', fontSize: 11, fontWeight: '700',
           letterSpacing: 0.6, marginBottom: 4 },
  tick: { position: 'absolute', right: 4, color: 'rgba(255,255,255,0.35)', fontSize: 9 },
});
