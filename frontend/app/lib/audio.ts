"use client";

import { useState, useRef, useCallback } from "react";
import toast from "react-hot-toast";

export type AgentState = "idle" | "listening" | "thinking" | "speaking";

export function useVoiceInterview(sessionId: string) {
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  
  // Audio playback queue
  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);

  const playNextInQueue = useCallback(() => {
    if (!audioContextRef.current || audioQueue.current.length === 0) {
      isPlayingRef.current = false;
      setAgentState(prev => prev === "speaking" ? "idle" : prev);
      return;
    }

    isPlayingRef.current = true;
    setAgentState("speaking");
    
    const buffer = audioQueue.current.shift();
    if (!buffer) return;

    const source = audioContextRef.current.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContextRef.current.destination);
    
    source.onended = () => {
      playNextInQueue();
    };
    
    source.start();
  }, [agentState]);

  const startInterview = useCallback(async () => {
    try {
      // 1. Get microphone permissions
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // 2. Initialize Audio Context for playback
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      
      // 3. Connect WebSocket (uses NEXT_PUBLIC_BACKEND_URL for production, localhost for dev)
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "localhost:8000";
      const wsProtocol = backendUrl.includes("localhost") ? "ws" : "wss";
      const wsUrl = `${wsProtocol}://${backendUrl}/interview/ws/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setAgentState("idle");
        toast.success("Connected to Interview Agent");
      };

      ws.onmessage = async (event) => {
        // We expect binary audio chunks from the backend (TTS)
        if (event.data instanceof Blob) {
          if (event.data.size === 0) {
            console.warn("Received empty audio chunk from backend. Ignoring.");
            return;
          }
          const arrayBuffer = await event.data.arrayBuffer();
          if (audioContextRef.current) {
            const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
            audioQueue.current.push(audioBuffer);
            if (!isPlayingRef.current) {
              playNextInQueue();
            }
          }
        }
      };

      ws.onerror = () => {
        toast.error("WebSocket connection error");
        stopInterview();
      };

      ws.onclose = () => {
        toast("Interview session ended", { icon: "👋" });
        stopInterview();
      };

      // 4. Setup MediaRecorder to send audio chunks to the backend
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(event.data);
        }
      };

      // In a real app, you might use a VAD (Voice Activity Detector) to toggle this.
      // For this simple implementation, we'll slice the audio every 2 seconds if the user is holding a "talk" button.
      // We will handle the actual recording start/stop in the UI components.

    } catch (err) {
      console.error(err);
      toast.error("Microphone access denied or error connecting.");
    }
  }, [sessionId, playNextInQueue]);

  const startRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "inactive") {
      mediaRecorderRef.current.start(2000); // Send chunks every 2 seconds while recording
      setAgentState("listening");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      // After user stops speaking, the agent is thinking...
      setAgentState("thinking");
    }
  }, []);

  const stopInterview = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    if (mediaRecorderRef.current) mediaRecorderRef.current.stream.getTracks().forEach(t => t.stop());
    setAgentState("idle");
  }, []);

  return {
    agentState,
    startInterview,
    stopInterview,
    startRecording,
    stopRecording
  };
}
