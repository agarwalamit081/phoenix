/**
 * LiveKit voice interaction hook using livekit-client.
 * Provides real-time voice interaction with WebRTC for better audio quality.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  AudioTrack,
  LocalParticipant,
  RemoteParticipant,
  Track,
} from "livekit-client";

export type VoiceState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

export interface VoiceTranscript {
  text: string;
  is_final: boolean;
  timestamp: number;
}

export interface UseLiveKitVoiceOptions {
  language?: string;
  onTranscript?: (transcript: VoiceTranscript) => void;
  onResponse?: (text: string) => void;
  onError?: (error: Error) => void;
  token?: string;
  roomUrl?: string;
}

export interface UseLiveKitVoiceReturn {
  state: VoiceState;
  transcript: string;
  isListening: boolean;
  isConnected: boolean;
  startListening: () => Promise<void>;
  stopListening: () => void;
  clearTranscript: () => void;
  error: Error | null;
}

/**
 * Hook for LiveKit-based voice interaction using WebRTC.
 *
 * @param options - Configuration options
 * @returns Voice state and control functions
 *
 * @example
 * ```tsx
 * const { state, startListening, stopListening, transcript, isConnected } = useLiveKitVoice({
 *   language: 'en',
 *   onTranscript: (t) => console.log(t.text),
 *   token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
 *   roomUrl: 'wss://test-gvg6iaq1.livekit.cloud',
 * });
 * ```
 */
export function useLiveKitVoice(options: UseLiveKitVoiceOptions = {}): UseLiveKitVoiceReturn {
  const {
    language = "en",
    onTranscript,
    onResponse,
    onError,
    token: initialToken,
    roomUrl: initialRoomUrl,
  } = options;

  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);

  const [room, setRoom] = useState<Room | null>(null);
  const roomRef = useRef<Room | null>(null); // ref so startListening can use it immediately after connect
  const [transcriptAccumulator, setTranscriptAccumulator] = useState("");

  // Connect to LiveKit room — returns the connected Room so callers can use it immediately
  const connectToRoom = useCallback(async (url: string, accessToken: string): Promise<Room | null> => {
    console.log('[useLiveKitVoice] Connecting to LiveKit room:', { url, hasToken: !!accessToken });

    try {
      setState("connecting");
      setError(null);

      // Create new room
      const newRoom = new Room();

      // Set up event listeners
      newRoom.on(RoomEvent.Connected, () => {
        console.log('[useLiveKitVoice] Connected to LiveKit room');
        setIsConnected(true);
        setState("idle");
      });

      newRoom.on(RoomEvent.Disconnected, (reason) => {
        console.log('[useLiveKitVoice] Disconnected from LiveKit room:', reason);
        setIsConnected(false);
        setIsListening(false);
        setState("idle");
      });

      newRoom.on(RoomEvent.ConnectionStateChanged, (state) => {
        console.log('[useLiveKitVoice] Connection state changed:', state);
      });

      // Handle data messages for transcripts
      newRoom.on(RoomEvent.DataReceived, (payload, participant) => {
        try {
          const data = JSON.parse(new TextDecoder().decode(payload));
          console.log('[useLiveKitVoice] Received data:', data);

          if (data.type === "transcript") {
            const transcriptData: VoiceTranscript = {
              text: data.data.text,
              is_final: data.data.is_final,
              timestamp: data.data.timestamp || Date.now(),
            };

            if (transcriptData.is_final) {
              setTranscriptAccumulator((prev) => {
                const updated = prev + " " + transcriptData.text;
                setTranscript(updated.trim());
                return updated.trim();
              });
            }

            onTranscript?.(transcriptData);
          } else if (data.type === "response") {
            const responseText = data.text || "";
            onResponse?.(responseText);
            setState("speaking");

            // Reset to listening after a delay
            setTimeout(() => {
              setState("listening");
            }, 3000);
          } else if (data.type === "error") {
            const error = new Error(data.message || "Unknown error");
            setError(error);
            onError?.(error);
            setState("error");
          }
        } catch (e) {
          console.error('[useLiveKitVoice] Failed to parse data message:', e);
        }
      });

      // Handle remote participants (voice agent)
      newRoom.on(RoomEvent.ParticipantConnected, (participant) => {
        console.log('[useLiveKitVoice] Remote participant connected:', participant.identity);
      });

      // Handle audio tracks from voice agent (TTS)
      newRoom.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        console.log('[useLiveKitVoice] Track subscribed:', track.kind);

        if (track.kind === Track.Kind.Audio) {
          const audioTrack = track as AudioTrack;
          audioTrack.attach();
          setState("speaking");
        }
      });

      newRoom.on(RoomEvent.TrackUnsubscribed, (track) => {
        console.log('[useLiveKitVoice] Track unsubscribed:', track.kind);
        if (track.kind === Track.Kind.Audio) {
          setState("listening");
        }
      });

      // Connect to the room
      await newRoom.connect(url, accessToken, {
        autoSubscribe: true,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      setRoom(newRoom);
      roomRef.current = newRoom;
      console.log('[useLiveKitVoice] Room connection complete');
      return newRoom;

    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[useLiveKitVoice] Connection error:', error);
      setError(error);
      setState("error");
      onError?.(error);
      return null;
    }
  }, [onTranscript, onResponse, onError]);

  // Publish microphone audio — accepts an explicit room so it works before React state updates
  const publishAudio = useCallback(async (targetRoom?: Room) => {
    const activeRoom = targetRoom ?? roomRef.current ?? room;
    if (!activeRoom) {
      console.warn('[useLiveKitVoice] No room to publish audio');
      return;
    }

    try {
      console.log('[useLiveKitVoice] Publishing microphone audio...');

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      await activeRoom.localParticipant.publishTrack(stream.getAudioTracks()[0], {
        name: "microphone",
      });

      console.log('[useLiveKitVoice] Microphone audio published');
      setIsListening(true);
      setState("listening");

    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[useLiveKitVoice] Failed to publish audio:', error);
      setError(error);
      onError?.(error);
    }
  }, [room, onError]);

  // Unpublish microphone audio
  const unpublishAudio = useCallback(async () => {
    const activeRoom = roomRef.current ?? room;
    if (!activeRoom) return;

    try {
      const tracks = activeRoom.localParticipant.getTrackPublications();
      for (const [_, track] of tracks) {
        if (track.kind === Track.Kind.Audio) {
          await activeRoom.localParticipant.unpublishTrack(track.trackSid);
        }
      }

      setIsListening(false);
      setState("idle");
      console.log('[useLiveKitVoice] Microphone audio unpublished');

    } catch (err) {
      console.error('[useLiveKitVoice] Failed to unpublish audio:', err);
    }
  }, [room]);

  // Start listening
  const startListening = useCallback(async () => {
    if (!initialToken || !initialRoomUrl) {
      const error = new Error("Token and room URL are required");
      setError(error);
      onError?.(error);
      return;
    }

    let activeRoom = roomRef.current;

    // Connect to room if not already connected
    if (!activeRoom || !isConnected) {
      activeRoom = await connectToRoom(initialRoomUrl, initialToken);
    }

    // Publish audio — pass the room directly so we don't wait for React state update
    if (activeRoom) {
      await publishAudio(activeRoom);
    }
  }, [initialToken, initialRoomUrl, isConnected, connectToRoom, publishAudio, onError]);

  // Stop listening
  const stopListening = useCallback(() => {
    unpublishAudio();
  }, [unpublishAudio]);

  // Clear transcript
  const clearTranscript = useCallback(() => {
    setTranscriptAccumulator("");
    setTranscript("");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const activeRoom = roomRef.current ?? room;
      if (activeRoom) {
        activeRoom.disconnect();
        roomRef.current = null;
      }
    };
  }, [room]);

  return {
    state,
    transcript,
    isListening,
    isConnected,
    startListening,
    stopListening,
    clearTranscript,
    error,
  };
}
