import React, { useMemo, useRef, useEffect, useState } from 'react';
import { chatAPI } from '@/services/api';

function canRecordAudioInBrowser(): boolean {
  return (
    typeof window !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
  );
}

function pickRecorderMimeType(): string | undefined {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/wav',
  ];
  for (const t of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(t)) return t;
    } catch {
      // ignore
    }
  }
  return undefined;
}

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  placeholder = 'Type your message...',
}) => {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const [sttEnabled, setSttEnabled] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [sttError, setSttError] = useState<string | null>(null);

  const sttAvailable = useMemo(() => canRecordAudioInBrowser(), []);

  useEffect(() => {
    let cancelled = false;
    if (!sttAvailable) return;

    chatAPI
      .sttEnabled()
      .then((res) => {
        if (!cancelled) setSttEnabled(!!res.enabled);
      })
      .catch(() => {
        if (!cancelled) setSttEnabled(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sttAvailable]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [value]);

  useEffect(() => {
    // If user releases pointer outside the mic button, still stop recording.
    if (!isRecording) return;
    const onPointerUp = () => {
      void stopRecordingAndTranscribe();
    };
    window.addEventListener('pointerup', onPointerUp);
    return () => window.removeEventListener('pointerup', onPointerUp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRecording]);

  const cleanupRecorder = () => {
    try {
      recorderRef.current?.stop();
    } catch {
      // ignore
    }
    recorderRef.current = null;

    const stream = streamRef.current;
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
    }
    streamRef.current = null;
    chunksRef.current = [];
  };

  const sendTranscript = (textRaw: string) => {
    const text = textRaw.trim();
    if (!text) return;
    if (disabled) return;

    onSend(text);
    setValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const startRecording = async () => {
    if (!sttAvailable || !sttEnabled) return;
    if (disabled || isTranscribing || isRecording) return;

    setSttError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = pickRecorderMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;

      recorder.ondataavailable = (evt) => {
        if (evt.data && evt.data.size > 0) chunksRef.current.push(evt.data);
      };

      recorder.onerror = () => {
        setSttError('Recording failed.');
        setIsRecording(false);
        cleanupRecorder();
      };

      recorder.onstop = () => {
        const blobType = mimeType || recorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: blobType });
        cleanupRecorder();
        void transcribeBlob(blob);
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Microphone permission denied.';
      setSttError(msg);
      setIsRecording(false);
      cleanupRecorder();
    }
  };

  const stopRecordingAndTranscribe = async () => {
    if (!isRecording) return;
    setIsRecording(false);
    const recorder = recorderRef.current;
    if (!recorder) {
      cleanupRecorder();
      return;
    }
    try {
      if (recorder.state !== 'inactive') recorder.stop();
    } catch {
      cleanupRecorder();
    }
  };

  const transcribeBlob = async (blob: Blob) => {
    if (!blob.size) return;
    if (disabled) return;

    setIsTranscribing(true);
    setSttError(null);
    try {
      const res = await chatAPI.transcribeAudio(blob);
      // Send to chat immediately once transcription is done.
      sendTranscript(res.text);
    } catch (err) {
      setSttError(err instanceof Error ? err.message : 'Transcription failed.');
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-700 bg-slate-900 p-4">
      <div className="flex gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-slate-600 bg-slate-800 text-slate-100 placeholder-slate-400 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed transition-all"
          style={{ maxHeight: '200px' }}
        />
        {sttAvailable && sttEnabled && (
          <button
            type="button"
            onPointerDown={(e) => {
              e.preventDefault();
              void startRecording();
            }}
            onPointerUp={(e) => {
              e.preventDefault();
              void stopRecordingAndTranscribe();
            }}
            disabled={disabled || isTranscribing}
            className={[
              'px-4 py-2 rounded-lg border transition-all duration-200 font-semibold shadow-lg select-none',
              isRecording
                ? 'bg-red-700 border-red-500 text-white'
                : 'bg-slate-800 border-slate-600 text-slate-100 hover:bg-slate-700',
              disabled || isTranscribing ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
            ].join(' ')}
            title={isRecording ? 'Release to stop' : 'Hold to talk'}
          >
            {isTranscribing ? '⏳' : isRecording ? '⏺' : '🎙️'}
          </button>
        )}
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="px-6 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:from-slate-700 disabled:to-slate-700 disabled:cursor-not-allowed transition-all duration-200 font-semibold shadow-lg"
        >
          {disabled ? '⏳ Sending...' : '🚀 Send'}
        </button>
      </div>
      <div className="mt-1 text-xs text-slate-400">
        {sttError ? (
          <span className="text-red-300">{sttError}</span>
        ) : (
          <span>Press Enter to send, Shift+Enter for new line</span>
        )}
      </div>
    </form>
  );
};
