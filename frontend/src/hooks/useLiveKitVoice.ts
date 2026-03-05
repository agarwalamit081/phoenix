/**
 * LiveKit voice interaction hook using livekit-client.
 * Provides real-time voice interaction with WebRTC for better audio quality.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  AudioTrack,
  Track,
  type TranscriptionSegment,
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
  const [transcriptAccumulator, setTranscriptAccumulator] = useState("");
  const roomRef = useRef<Room | null>(null);
  const startInFlightRef = useRef(false);
  const seenFinalSegmentsRef = useRef<Set<string>>(new Set());

  // Connect to LiveKit room
  const connectToRoom = useCallback(async (url: string, accessToken: string): Promise<Room | null> => {
    console.log('[useLiveKitVoice] Connecting to LiveKit room:', { url, hasToken: !!accessToken });

    try {
      if (roomRef.current) {
        console.log("[useLiveKitVoice] Reusing existing room instance");
        return roomRef.current;
      }

      setState("connecting");
      setError(null);

      // Create new room
      const newRoom = new Room();
      roomRef.current = newRoom;

      // Create a promise that resolves when connected
      const connectionPromise = new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("Connection timeout"));
        }, 10000);

        newRoom.on(RoomEvent.Connected, () => {
          clearTimeout(timeout);
          console.log('[useLiveKitVoice] Connected to LiveKit room');
          setIsConnected(true);
          setState("idle");
          setRoom(newRoom);
          roomRef.current = newRoom;
          resolve();
        });

        newRoom.on(RoomEvent.Disconnected, (reason) => {
          clearTimeout(timeout);
          console.log('[useLiveKitVoice] Disconnected from LiveKit room:', reason);
          setIsConnected(false);
          setIsListening(false);
          setState("idle");
          setRoom(null);
          if (roomRef.current === newRoom) {
            roomRef.current = null;
          }
        });
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

      // Handle native LiveKit transcription events.
      // This is the primary path for agent-transcribed user speech in current worker setup.
      newRoom.on(
        RoomEvent.TranscriptionReceived,
        (segments: TranscriptionSegment[], participant) => {
          for (const segment of segments) {
            const text = (segment.text || "").trim();
            if (!text) {
              continue;
            }

            const segmentKey = `${participant?.identity || "unknown"}:${segment.id}`;
            if (!segment.final || seenFinalSegmentsRef.current.has(segmentKey)) {
              continue;
            }
            seenFinalSegmentsRef.current.add(segmentKey);

            const transcriptData: VoiceTranscript = {
              text,
              is_final: true,
              timestamp: Date.now(),
            };

            // Agent text should be surfaced as response; user text as transcript.
            const fromAgent = Boolean(
              participant && participant.identity !== newRoom.localParticipant.identity
            );
            if (fromAgent) {
              onResponse?.(text);
              setState("speaking");
              setTimeout(() => {
                setState("listening");
              }, 1200);
            } else {
              setTranscriptAccumulator((prev) => {
                const updated = prev ? `${prev}\n${text}` : text;
                setTranscript(updated);
                return updated;
              });
              onTranscript?.(transcriptData);
            }
          }
        }
      );

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
        }
      });

      newRoom.on(RoomEvent.TrackUnsubscribed, (track) => {
        console.log('[useLiveKitVoice] Track unsubscribed:', track.kind);
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

      // Wait for the connection to be established
      await connectionPromise;

      console.log('[useLiveKitVoice] Room connection complete');
      return newRoom;

    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('[useLiveKitVoice] Connection error:', error);
      setError(error);
      setState("error");
      if (roomRef.current) {
        try {
          roomRef.current.disconnect();
        } catch {
          // no-op
        }
      }
      roomRef.current = null;
      setRoom(null);
      onError?.(error);
      return null;
    }
  }, [onTranscript, onResponse, onError]);

  // Publish microphone audio
  const publishAudio = useCallback(async () => {
    if (!room) {
      console.warn('[useLiveKitVoice] No room to publish audio');
      return;
    }

    try {
      console.log('[useLiveKitVoice] Publishing microphone audio...');

      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      // Publish audio track to room
      await room.localParticipant.publishTrack(stream.getAudioTracks()[0], {
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
    if (!room) return;

    try {
      const publications = room.localParticipant.getTrackPublications();
      for (const publication of publications) {
        if (publication.kind === Track.Kind.Audio && publication.track) {
          await room.localParticipant.unpublishTrack(publication.track);
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
    if (startInFlightRef.current) {
      console.log("[useLiveKitVoice] startListening ignored: already in progress");
      return;
    }

    if (!initialToken || !initialRoomUrl) {
      const error = new Error("Token and room URL are required");
      setError(error);
      onError?.(error);
      return;
    }

    if (isListening) {
      return;
    }

    startInFlightRef.current = true;
    try {
      let connectedRoom = roomRef.current;

      // Connect to room if not connected and wait for connection
      if (!connectedRoom || !isConnected) {
        connectedRoom = await connectToRoom(initialRoomUrl, initialToken);
        if (!connectedRoom) {
          console.error("[useLiveKitVoice] Failed to connect to room");
          return;
        }
      }

      // Publish audio using the connected room
      const hasPublishedAudio = connectedRoom
        .localParticipant
        .getTrackPublications()
        .some((publication) => publication.kind === Track.Kind.Audio);

      if (!hasPublishedAudio) {
        console.log("[useLiveKitVoice] Publishing microphone audio...");

        // Get user media
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });

        // Publish audio track to room
        await connectedRoom.localParticipant.publishTrack(stream.getAudioTracks()[0], {
          name: "microphone",
        });

        console.log("[useLiveKitVoice] Microphone audio published");
      } else {
        console.log("[useLiveKitVoice] Reusing existing published microphone track");
      }

      setIsListening(true);
      setState("listening");
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error("[useLiveKitVoice] Failed to publish audio:", error);
      setError(error);
      onError?.(error);
      setState("error");
    } finally {
      startInFlightRef.current = false;
    }
  }, [initialToken, initialRoomUrl, isConnected, isListening, connectToRoom, onError]);

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
      if (room) {
        room.disconnect();
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
