/**
 * Scrolling live mel-spectrogram rendered with Skia.
 *
 * Decoupled from the audio source: the parent feeds mel columns imperatively via
 * the ref (`pushColumns`), and this component keeps the most recent HISTORY_COLS
 * of them, packs them to an RGBA image (via the pure helpers in ml/spectrogram),
 * and blits that scaled to fill the canvas. A requestAnimationFrame loop throttles
 * redraws so a burst of columns doesn't trigger a React render per column.
 *
 * x = time (newest at right), y = frequency (low at bottom), colour = energy.
 */
import React, {
  forwardRef, useEffect, useImperativeHandle, useRef, useState,
} from 'react';
import { View, StyleSheet } from 'react-native';
import {
  Canvas, Image, Skia, AlphaType, ColorType, type SkImage,
} from '@shopify/react-native-skia';

import { packColumnsToRGBA } from '../ml/spectrogram';

export type LiveSpectrogramHandle = {
  /** Append newly-computed mel columns (each Float32Array[nMels], values 0..1). */
  pushColumns: (cols: Float32Array[]) => void;
  /** Drop all history (e.g. when a session stops). */
  clear: () => void;
};

type Props = {
  nMels: number;
  width: number;
  height: number;
  /** Number of time columns kept on screen (wider = longer time window). */
  historyCols?: number;
  style?: object;
};

function buildImage(columns: Float32Array[], nMels: number): SkImage | null {
  const { bytes, width, height } = packColumnsToRGBA(columns, nMels);
  const data = Skia.Data.fromBytes(bytes);
  return Skia.Image.MakeImage(
    { width, height, colorType: ColorType.RGBA_8888, alphaType: AlphaType.Opaque },
    data,
    width * 4,
  );
}

export const LiveSpectrogram = forwardRef<LiveSpectrogramHandle, Props>(
  ({ nMels, width, height, historyCols = 256, style }, ref) => {
    const colsRef = useRef<Float32Array[]>([]);
    const dirtyRef = useRef(false);
    const [image, setImage] = useState<SkImage | null>(null);

    useImperativeHandle(ref, () => ({
      pushColumns: (cols) => {
        if (!cols.length) return;
        const buf = colsRef.current;
        for (const c of cols) buf.push(c);
        if (buf.length > historyCols) buf.splice(0, buf.length - historyCols);
        dirtyRef.current = true;
      },
      clear: () => { colsRef.current = []; dirtyRef.current = true; },
    }), [historyCols]);

    // Throttle image rebuilds to the display refresh rate.
    useEffect(() => {
      let raf = 0;
      let alive = true;
      const loop = () => {
        if (!alive) return;
        if (dirtyRef.current) {
          dirtyRef.current = false;
          setImage(colsRef.current.length ? buildImage(colsRef.current, nMels) : null);
        }
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
      return () => { alive = false; cancelAnimationFrame(raf); };
    }, [nMels]);

    return (
      <View style={[styles.container, { width, height }, style]}>
        <Canvas style={{ width, height }}>
          {image && (
            <Image image={image} x={0} y={0} width={width} height={height} fit="fill" />
          )}
        </Canvas>
      </View>
    );
  },
);

LiveSpectrogram.displayName = 'LiveSpectrogram';

const styles = StyleSheet.create({
  container: { overflow: 'hidden', borderRadius: 12, backgroundColor: '#000' },
});
