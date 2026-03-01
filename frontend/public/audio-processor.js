/**
 * AudioWorkletProcessor — streams PCM-16 at 16 kHz to the main thread.
 *
 * The browser will call process() every 128 samples at the AudioContext sample rate.
 * We accumulate samples and downsample to 16 kHz before posting.
 */
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._targetRate = 16000;
    this._chunkSamples = 1280; // 80 ms chunks at 16 kHz — lower latency than 256 ms
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0]; // Float32, mono, at context sampleRate
    const inputRate = sampleRate; // AudioWorkletGlobalScope provides this

    // Linear-interpolation downsample: compute correct OUTPUT length first
    const ratio = inputRate / this._targetRate;
    const outLen = Math.ceil(channelData.length / ratio);
    for (let i = 0; i < outLen; i++) {
      const srcIdx = i * ratio;
      const lo = Math.floor(srcIdx);
      const hi = Math.min(lo + 1, channelData.length - 1);
      const frac = srcIdx - lo;
      const sample = channelData[lo] * (1 - frac) + channelData[hi] * frac;
      this._buffer.push(sample);
    }

    // Flush when we have enough samples
    while (this._buffer.length >= this._chunkSamples) {
      const chunk = this._buffer.splice(0, this._chunkSamples);
      // Convert Float32 → Int16
      const pcm16 = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    return true; // keep processor alive
  }
}

registerProcessor("pcm16-processor", PCM16Processor);
