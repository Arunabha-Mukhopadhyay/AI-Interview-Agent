"use client";

import React, { useEffect, useState } from "react";
import { use, useMemo } from "react";
import { motion, Variants } from "framer-motion";
import { Mic, Square, Loader2, Phone } from "lucide-react";
import { GlassCard } from "@/app/components/ui/GlassCard";
import { Button } from "@/app/components/ui/Button";
import { useVoiceInterview, AgentState } from "@/app/lib/audio";
import { Toaster } from "react-hot-toast";

// App router dynamic params are Promises in Next.js 15+
export default function InterviewRoom({ params }: { params: Promise<{ session_id: string }> }) {
  // Unwrap params using React.use()
  const resolvedParams = use(params);
  const sessionId = resolvedParams.session_id;

  const {
    agentState,
    startInterview,
    stopInterview,
    startRecording,
    stopRecording
  } = useVoiceInterview(sessionId);

  const [hasStarted, setHasStarted] = useState(false);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopInterview();
    };
  }, [stopInterview]);

  const handleStart = async () => {
    await startInterview();
    setHasStarted(true);
  };

  // Orb animation states based on agent state
  const orbVariants: Variants = useMemo(() => ({
    idle: { scale: 1, opacity: 0.5, boxShadow: "0px 0px 20px rgba(59, 130, 246, 0.2)" },
    listening: { 
      scale: [1, 1.1, 1], 
      opacity: 0.8,
      boxShadow: ["0px 0px 20px rgba(168, 85, 247, 0.4)", "0px 0px 40px rgba(168, 85, 247, 0.8)", "0px 0px 20px rgba(168, 85, 247, 0.4)"],
      transition: { repeat: Infinity, duration: 1.5 }
    },
    thinking: { 
      scale: 1, 
      opacity: [0.4, 0.8, 0.4],
      boxShadow: "0px 0px 20px rgba(234, 179, 8, 0.4)",
      transition: { repeat: Infinity, duration: 1 }
    },
    speaking: { 
      scale: [1, 1.2, 1.1, 1.3, 1], 
      opacity: 1,
      boxShadow: "0px 0px 60px rgba(59, 130, 246, 0.8)",
      transition: { repeat: Infinity, duration: 0.8, ease: "easeInOut" }
    }
  }), []);

  const stateLabels: Record<AgentState, string> = {
    idle: "Waiting...",
    listening: "Listening to you...",
    thinking: "Thinking...",
    speaking: "Agent is speaking"
  };

  if (!hasStarted) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 overflow-hidden relative">
        <Toaster position="top-center" />
        <GlassCard className="max-w-md w-full items-center text-center">
          <div className="w-20 h-20 bg-blue-500/20 rounded-full flex items-center justify-center mb-4 mx-auto">
            <Phone className="w-8 h-8 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Ready to begin?</h1>
          <p className="text-slate-400 text-sm mt-2 mb-6">
            Make sure you are in a quiet environment. The AI will introduce itself as soon as you connect.
          </p>
          <Button onClick={handleStart} className="w-full h-12 text-base">
            Join Interview Room
          </Button>
        </GlassCard>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4 overflow-hidden relative">
      <Toaster position="top-center" />
      
      {/* Background gradients */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60%] h-[60%] rounded-full bg-blue-600/10 blur-[120px]" />
      
      <div className="z-10 flex flex-col items-center w-full max-w-lg gap-12">
        {/* The Orb */}
        <div className="relative w-64 h-64 flex items-center justify-center">
          <motion.div
            variants={orbVariants}
            animate={agentState}
            className={`w-32 h-32 rounded-full absolute ${
              agentState === 'listening' ? 'bg-purple-500' :
              agentState === 'thinking' ? 'bg-yellow-500' :
              'bg-blue-500'
            }`}
          />
          {/* Inner core */}
          <div className="w-24 h-24 bg-slate-900 rounded-full absolute border border-white/10 z-10 flex items-center justify-center">
             {agentState === 'thinking' && <Loader2 className="w-6 h-6 text-yellow-400 animate-spin" />}
          </div>
        </div>

        {/* Status Text */}
        <motion.div 
          key={agentState}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-xl font-medium text-slate-200"
        >
          {stateLabels[agentState]}
        </motion.div>

        {/* Controls */}
        <GlassCard className="w-full flex-row justify-center gap-6 p-4 md:p-6 rounded-[2rem]">
          <Button
            variant={agentState === "listening" ? "danger" : "primary"}
            className="w-20 h-20 rounded-full !p-0"
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onMouseLeave={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            disabled={agentState === "speaking" || agentState === "thinking"}
          >
            {agentState === "listening" ? (
              <Square className="w-8 h-8" fill="currentColor" />
            ) : (
              <Mic className="w-8 h-8" />
            )}
          </Button>
          <div className="text-center w-full absolute -bottom-10 left-0 text-slate-500 text-sm">
            Hold to speak
          </div>
        </GlassCard>
      </div>
    </main>
  );
}
