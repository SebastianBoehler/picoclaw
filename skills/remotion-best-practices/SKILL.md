---
name: remotion-best-practices
description: Best practices for Remotion - Video creation in React. Use whenever dealing with Remotion code for animations, compositions, audio, video, captions, transitions, and rendering.
---

# Remotion Best Practices

## When to Use
Use whenever dealing with Remotion code for video creation in React.

## Core Rules
- Use `useCurrentFrame()` and `useVideoConfig()` for all timing
- Use `interpolate()` for linear/easing, `spring()` for physics animations
- Always clamp: `extrapolateLeft: 'clamp', extrapolateRight: 'clamp'`
- Never use `Math.random()` — use `random()` from remotion (deterministic)
- Never use `Date.now()` or `new Date()` — use frame-based timing
- Never use CSS `transition` or `animation` — use Remotion's interpolation
- Always use `staticFile()` for local assets, never raw paths
- Use `<Img>` not `<img>`, `<Video>` not `<video>`, `<Audio>` not `<audio>`

## Animations
```tsx
import { useCurrentFrame, interpolate, spring, useVideoConfig } from 'remotion';

const frame = useCurrentFrame();
const { fps } = useVideoConfig();

const opacity = interpolate(frame, [0, 30], [0, 1], {
  extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
});
const scale = spring({ frame, fps, config: { damping: 10 } });
```

## Sequencing
```tsx
<Sequence from={30} durationInFrames={60}>
  <MyComponent />
</Sequence>
```

## Transitions
```tsx
import { TransitionSeries, fade } from '@remotion/transitions';
import { linearTiming } from '@remotion/transitions';

<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={60}><SceneA /></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 30 })} />
  <TransitionSeries.Sequence durationInFrames={60}><SceneB /></TransitionSeries.Sequence>
</TransitionSeries>
```

## Audio Visualization
```tsx
import { useAudioData, visualizeAudio } from '@remotion/media-utils';
const audioData = useAudioData(staticFile('audio.mp3'));
const visualization = visualizeAudio({ fps, frame, audioData, numberOfSamples: 256 });
```

## Fonts
```tsx
import { loadFont } from '@remotion/google-fonts/Inter';
const { fontFamily } = loadFont();
```

## Rendering
```bash
npx remotion render src/index.ts MyComposition out/video.mp4
npx remotion still src/index.ts MyComposition --frame=30 out/still.png
```

## Common Pitfalls
- Async asset loading: always use `delayRender()` / `continueRender()`
- FFmpeg operations: only in scripts/CLI, never inside React components
- For captions/subtitles: use `@remotion/captions`
- For 3D: use `@remotion/three` with `<ThreeCanvas>`
- For Lottie: use `@remotion/lottie`
