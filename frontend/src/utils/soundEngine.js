/**
 * محرك صوتي اصطناعي بالكامل عبر Web Audio — بدون ملفات MP3.
 * - يُنشئ AudioContext مرة واحدة فقط بعد أول تفاعل مستخدم.
 * - كل الأصوات محاطة بـ try/catch، وفشل الصوت لا يوقف اللعب أبدًا.
 * - يمكن كتمه أو التخلص منه بالكامل.
 */
class SoundEngine {
  constructor() {
    this.context = null;
    this.master = null;
    this.muted = false;
    this.disposed = false;
    this.noiseBuffer = null;
  }

  setMuted(muted) {
    this.muted = Boolean(muted);
    if (this.master && this.context) {
      try {
        this.master.gain.setTargetAtTime(this.muted ? 0 : 0.22, this.context.currentTime, 0.02);
      } catch {
        // تجاهل؛ الصوت غير حرج للعب.
      }
    }
  }

  isSupported() {
    return typeof window !== 'undefined' && Boolean(window.AudioContext || window.webkitAudioContext);
  }

  async ensureContext() {
    if (this.disposed || this.muted || !this.isSupported()) return null;
    try {
      if (!this.context) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.context = new AudioCtx();
        this.master = this.context.createGain();
        this.master.gain.value = 0.22;
        this.master.connect(this.context.destination);
      }
      if (this.context.state === 'suspended') {
        await this.context.resume();
      }
      return this.context;
    } catch {
      return null;
    }
  }

  async unlock() {
    await this.ensureContext();
  }

  dispose() {
    this.disposed = true;
    try {
      if (this.context && this.context.state !== 'closed') {
        this.context.close();
      }
    } catch {
      // تجاهل.
    }
    this.context = null;
    this.master = null;
    this.noiseBuffer = null;
  }

  tone({ freq, duration = 0.15, type = 'sine', volume = 0.5, delay = 0, glideTo = null }) {
    const ctx = this.context;
    if (!ctx || !this.master || this.muted) return;
    try {
      const start = ctx.currentTime + delay;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, start);
      if (glideTo) osc.frequency.exponentialRampToValueAtTime(Math.max(20, glideTo), start + duration);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, volume), start + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      osc.connect(gain);
      gain.connect(this.master);
      osc.start(start);
      osc.stop(start + duration + 0.03);
    } catch {
      // الصوت اختياري.
    }
  }

  async tick() {
    await this.ensureContext();
    this.tone({ freq: 880, duration: 0.06, type: 'triangle', volume: 0.18 });
  }

  /** Broadcast-style two-tone cue for turn changes on the board. */
  async turn() {
    await this.ensureContext();
    this.tone({ freq: 660, duration: 0.12, type: 'triangle', volume: 0.28 });
    this.tone({ freq: 880, duration: 0.18, type: 'triangle', volume: 0.28, delay: 0.1 });
  }

  async buzzer() {
    await this.ensureContext();
    this.tone({ freq: 240, glideTo: 110, duration: 0.4, type: 'sawtooth', volume: 0.5 });
    this.tone({ freq: 180, glideTo: 90, duration: 0.4, type: 'square', volume: 0.2, delay: 0.02 });
  }

  async stealAlarm() {
    await this.ensureContext();
    [0, 0.22, 0.44].forEach((delay, index) => {
      this.tone({
        freq: index % 2 === 0 ? 740 : 520,
        duration: 0.16,
        type: 'square',
        volume: 0.26,
        delay,
      });
    });
  }

  async power() {
    await this.ensureContext();
    [392, 523, 659, 784].forEach((freq, index) => {
      this.tone({ freq, duration: 0.14, type: 'triangle', volume: 0.3, delay: index * 0.055 });
    });
  }

  async score() {
    await this.ensureContext();
    [523, 659, 784].forEach((freq, index) => {
      this.tone({ freq, duration: 0.22, type: 'sine', volume: 0.32, delay: index * 0.08 });
    });
  }

  async shatter() {
    await this.ensureContext();
    if (!this.context || !this.master || this.muted) return;
    try {
      if (!this.noiseBuffer) {
        const length = Math.floor(this.context.sampleRate * 0.3);
        const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < length; i += 1) {
          data[i] = (Math.random() * 2 - 1) * (1 - i / length);
        }
        this.noiseBuffer = buffer;
      }
      const source = this.context.createBufferSource();
      const gain = this.context.createGain();
      const filter = this.context.createBiquadFilter();
      filter.type = 'highpass';
      filter.frequency.value = 600;
      source.buffer = this.noiseBuffer;
      gain.gain.value = 0.4;
      source.connect(filter);
      filter.connect(gain);
      gain.connect(this.master);
      source.start();
    } catch {
      // تجاهل.
    }
  }

  async victory() {
    await this.ensureContext();
    const notes = [523, 659, 784, 1047, 784, 1047];
    notes.forEach((freq, index) => {
      this.tone({
        freq,
        duration: index === notes.length - 1 ? 0.7 : 0.2,
        type: 'triangle',
        volume: 0.32,
        delay: index * 0.13,
      });
    });
  }
}

export const soundEngine = new SoundEngine();
export default soundEngine;
