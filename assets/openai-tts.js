(function () {
  const DEFAULT_BASE_PATH = "audio/openai-tts";
  const DEFAULT_VOICE = "coral";

  let currentAudio = null;

  function normalizeText(text) {
    return String(text || "").replace(/\s+/g, " ").trim();
  }

  function normalizeLang(lang) {
    return String(lang || "en-US").toLowerCase();
  }

  function fnv1a(value) {
    let hash = 0x811c9dc5;
    for (let i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function audioPath(text, options) {
    const settings = options || {};
    const lang = normalizeLang(settings.lang);
    const voice = settings.voice || DEFAULT_VOICE;
    const basePath = settings.basePath || DEFAULT_BASE_PATH;
    const key = `${lang}|${voice}|${normalizeText(text)}`;
    return `${basePath}/${lang}/${fnv1a(key)}.mp3`;
  }

  function stop() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }

  function fallbackSpeech(text, options) {
    const settings = options || {};
    if (!("speechSynthesis" in window)) {
      if (settings.onDone) window.setTimeout(settings.onDone, 0);
      return false;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = settings.lang || "en-US";
    utterance.rate = settings.rate || 0.85;
    utterance.pitch = settings.pitch || 1;
    utterance.onend = utterance.onerror = () => {
      if (settings.onDone) settings.onDone();
    };
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function speak(text, options) {
    const cleanText = normalizeText(text);
    if (!cleanText) return null;

    const settings = options || {};
    stop();

    const src = settings.src || audioPath(cleanText, settings);
    const audio = new Audio(src);
    currentAudio = audio;
    audio.preload = "auto";
    audio.onended = () => {
      if (currentAudio === audio) currentAudio = null;
      if (settings.onDone) settings.onDone();
    };
    audio.onerror = () => {
      if (currentAudio === audio) currentAudio = null;
      fallbackSpeech(cleanText, settings);
    };
    audio.play().catch(() => {
      if (currentAudio === audio) currentAudio = null;
      fallbackSpeech(cleanText, settings);
    });
    return audio;
  }

  window.OpenAITTS = {
    audioPath,
    speak,
    stop
  };
}());
