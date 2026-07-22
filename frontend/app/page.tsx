"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Code, Link as LinkIcon, FileText, Briefcase, Upload } from "lucide-react";
import { GlassCard } from "@/app/components/ui/GlassCard";
import { Button } from "@/app/components/ui/Button";
import { Input } from "@/app/components/ui/Input";
import { Textarea } from "@/app/components/ui/Textarea";
import toast, { Toaster } from "react-hot-toast";

export default function UploadPage() {
  const router = useRouter();
  
  const [file, setFile] = useState<File | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Please upload a resume PDF.");
      return;
    }
    if (!jobDescription.trim()) {
      toast.error("Please provide a Job Description.");
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append("resume", file);
    formData.append("jd_text", jobDescription);
    if (githubUrl) formData.append("github_url", githubUrl);
    if (linkedinUrl) formData.append("linkedin_url", linkedinUrl);

    try {
      const response = await fetch("http://localhost:8000/ingest", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to process profile data.");
      }

      const data = await response.json();
      toast.success("Profile processed successfully!");
      
      // Navigate to the interview room
      router.push(`/interview/${data.session_id}`);
    } catch (error) {
      console.error(error);
      toast.error("Something went wrong processing your profile.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 sm:p-8 overflow-hidden relative">
      {/* Background gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/20 blur-[120px]" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px]" />

      <Toaster position="top-center" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="w-full max-w-2xl z-10"
      >
        <GlassCard>
          <div className="text-center space-y-2 mb-4">
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              AI Interview Agent
            </h1>
            <p className="text-slate-400 text-sm">
              Upload your profile and job description to begin your personalized technical interview.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Resume Upload */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300 ml-1">Resume (PDF)</label>
              <div className="relative">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="resume-upload"
                />
                <label
                  htmlFor="resume-upload"
                  className="glass-input w-full rounded-xl px-4 py-3 text-sm text-slate-100 flex items-center justify-between cursor-pointer hover:bg-slate-800/60 transition-colors"
                >
                  <div className="flex items-center gap-3 text-slate-400">
                    <FileText className="w-5 h-5 text-blue-400" />
                    <span className={file ? "text-slate-200" : ""}>
                      {file ? file.name : "Choose a PDF file..."}
                    </span>
                  </div>
                  <Upload className="w-4 h-4 text-slate-500" />
                </label>
              </div>
            </div>

            {/* GitHub URL */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300 ml-1">GitHub Profile URL (Optional)</label>
              <Input
                icon={<Code className="w-5 h-5 text-slate-400" />}
                type="url"
                placeholder="https://github.com/username"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
              />
            </div>

            {/* LinkedIn URL */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300 ml-1">LinkedIn Profile URL (Optional)</label>
              <Input
                icon={<LinkIcon className="w-5 h-5 text-slate-400" />}
                type="url"
                placeholder="https://linkedin.com/in/username"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
              />
            </div>

            {/* Job Description */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300 ml-1">Job Description</label>
              <div className="relative">
                <div className="absolute left-3 top-3 text-slate-400">
                  <Briefcase className="w-5 h-5" />
                </div>
                <Textarea
                  placeholder="Paste the requirements here..."
                  className="pl-10 h-32"
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-12 text-base mt-4"
              isLoading={isSubmitting}
            >
              {isSubmitting ? "Processing Profile..." : "Start Interview"}
            </Button>
          </form>
        </GlassCard>
      </motion.div>
    </main>
  );
}
