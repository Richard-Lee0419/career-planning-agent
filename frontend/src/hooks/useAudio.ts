import { useCallback, useEffect, useRef, useState } from 'react';

export function useAudioRecorder(onRecorded: (blob: Blob) => void | Promise<void>) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const [recording, setRecording] = useState(false);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  useEffect(() => () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const start = useCallback(async () => {
    setPermissionError(null);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream);
    } catch (error) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      throw error;
    }
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recorderRef.current = null;
      void onRecorded(blob);
    };
    recorder.start();
    setRecording(true);
  }, [onRecorded]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    setRecording(false);
  }, []);

  const toggle = useCallback(async () => {
    try {
      if (recording) {
        stop();
      } else {
        await start();
      }
    } catch {
      setPermissionError('麦克风不可用或权限被拒绝');
      setRecording(false);
    }
  }, [recording, start, stop]);

  return { recording, permissionError, toggle, stop };
}
