"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";

export default function Home() {
  const [jd, setJd] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<"checking" | "available" | "unavailable">("checking");
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const startJob = async () => {
    if (!files || !jd) {
      setError("Please add JD and upload resumes.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResults([]);
      setProgress(0);

      // Clear any existing polling
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      const formData = new FormData();
      formData.append("jd", jd);

      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }

      const res = await axios.post(
        "http://127.0.0.1:8000/start-job",
        formData,
        {
          timeout: 60000, // Increased timeout for file uploads
          headers: {
            'Content-Type': 'multipart/form-data',
          }
        }
      );

      const id = res.data.job_id;
      setJobId(id);

      pollStatus(id);
    } catch (err) {
      console.error("Job start error:", err);
      setLoading(false);
      if (axios.isAxiosError(err)) {
        if (err.code === 'ECONNREFUSED' || err.code === 'NETWORK_ERROR') {
          setError("Cannot connect to backend. Please ensure the server is running on http://127.0.0.1:8000");
        } else if (err.response?.status === 429) {
          setError("Too many requests. Please try again later.");
        } else if (err.code === 'ECONNABORTED') {
          setError("Request timed out. Please try again.");
        } else if (err.response?.status === 400) {
          setError(`Invalid request: ${err.response?.data?.detail || 'Please check your input'}`);
        } else if (err.response?.status === 500) {
          setError("Server error. Please try again later.");
        } else {
          setError(`Backend error: ${err.response?.data?.detail || err.message}`);
        }
      } else {
        setError("Unexpected error occurred. Please try again.");
      }
    }
  };

  const pollStatus = (id: number) => {
    let retryCount = 0;
    const maxRetries = 10;  // Increased max retries
    let consecutiveFailures = 0;
    let lastSuccessTime = Date.now();
    const maxConsecutiveFailures = 5;
    
    // Function to check server health
    const healthCheck = async () => {
      try {
        const res = await axios.get("http://127.0.0.1:8000/", { timeout: 3000 });
        return res.status === 200;
      } catch {
        return false;
      }
    };

    const poll = async () => {
      try {
        const res = await axios.get(
          `http://127.0.0.1:8000/job-status/${id}`,
          {
            timeout: 10000,  // Increased timeout
          }
        );

        const data = res.data;
        const percent =
          data.total === 0
            ? 0
            : (data.processed / data.total) * 100;

        setProgress(percent);
        setResults(data.candidates || []);
        retryCount = 0; // Reset retry count on success
        consecutiveFailures = 0; // Reset consecutive failures
        lastSuccessTime = Date.now();

        if (data.status === "completed") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setLoading(false);
        } else if (data.status === "failed") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setError("Job processing failed. Please try again.");
          setLoading(false);
        } else if (data.status === "completed_with_errors") {
          console.log("Job completed with some errors, continuing...");
        }
      } catch (err) {
        console.error("Polling error:", err);
        retryCount++;
        consecutiveFailures++;
        
        if (axios.isAxiosError(err)) {
          if (err.code === 'ECONNREFUSED' || err.code === 'NETWORK_ERROR') {
            // Try health check before giving up
            const isHealthy = await healthCheck();
            if (!isHealthy && consecutiveFailures >= maxConsecutiveFailures) {
              if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
              }
              setError("Backend server is down. Please start the backend server and refresh the page.");
              setLoading(false);
              return;
            }
          } else if (err.code === 'ECONNABORTED') {
            // Timeout - increase timeout temporarily
            if (retryCount > 5) {
              console.log("Multiple timeouts detected, slowing down polling");
              // The interval will be adjusted below
            }
          } else if (err.response?.status === 404) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            setError("Job not found. Please start a new analysis.");
            setLoading(false);
            return;
          }
          
          // If we've had many retries but some successes, be more lenient
          const timeSinceLastSuccess = Date.now() - lastSuccessTime;
          if (retryCount >= maxRetries && timeSinceLastSuccess > 30000) { // 30 seconds without success
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            setError("Connection lost for too long. Please refresh the page and try again.");
            setLoading(false);
            return;
          }
        }
        
        // Implement exponential backoff for intervals
        if (consecutiveFailures > 2 && intervalRef.current) {
          clearInterval(intervalRef.current);
          const backoffInterval = Math.min(3000 * Math.pow(1.5, consecutiveFailures - 2), 15000); // Max 15s
          console.log(`Implementing backoff: ${backoffInterval}ms due to ${consecutiveFailures} consecutive failures`);
          intervalRef.current = setInterval(poll, backoffInterval);
        }
      }
    };

    // Start polling immediately
    poll();
    intervalRef.current = setInterval(poll, 3000);
  };

  // Check LLM service status
  useEffect(() => {
    const checkLlmStatus = async () => {
      try {
        const res = await axios.get("http://127.0.0.1:8000/", { timeout: 3000 });
        if (res.status === 200) {
          setLlmStatus("available");
        }
      } catch (err) {
        setLlmStatus("unavailable");
      }
    };

    checkLlmStatus();
    // Check LLM status every 30 seconds
    const interval = setInterval(checkLlmStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-blue-100 to-indigo-100 text-gray-900 p-8">
      <div className="max-w-4xl mx-auto bg-white/95 backdrop-blur-sm p-10 rounded-2xl shadow-xl border border-blue-200">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-2">
            HR Resume Analyzer
          </h1>
          <div className="flex items-center justify-center space-x-2">
            <p className="text-gray-600">AI-powered candidate evaluation and ranking</p>
            {/* LLM Status Indicator */}
            <div className="flex items-center space-x-1">
              {llmStatus === "checking" && (
                <>
                  <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                  <span className="text-xs text-yellow-600">Checking AI...</span>
                </>
              )}
              {llmStatus === "available" && (
                <>
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  <span className="text-xs text-green-600">AI Ready</span>
                </>
              )}
              {llmStatus === "unavailable" && (
                <>
                  <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                  <span className="text-xs text-red-600">AI Offline (Using Fallback)</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* JD Input */}
        <div className="mb-6">
          <label className="block mb-2 font-semibold text-gray-700 flex items-center">
            <span className="bg-blue-100 text-blue-600 p-2 rounded-lg mr-2">
              📋
            </span>
            Job Description
          </label>
          <textarea
            className="w-full border-2 border-gray-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-200 p-4 mb-4 rounded-xl text-gray-900 bg-white/50 backdrop-blur-sm transition-all duration-200 resize-none"
            rows={6}
            placeholder="Enter job requirements, skills needed, experience level, etc..."
            value={jd}
            onChange={(e) => setJd(e.target.value)}
          />
        </div>

        {/* File Upload */}
        <div className="mb-6">
          <label className="block mb-2 font-semibold text-gray-700 flex items-center">
            <span className="bg-blue-100 text-blue-600 p-2 rounded-lg mr-2">
              📁
            </span>
            Upload Resumes
          </label>
          <div className="relative">
            <input
              type="file"
              multiple
              accept=".pdf,.doc,.docx"
              className="hidden"
              id="file-upload"
              onChange={(e) => setFiles(e.target.files)}
            />
            <label
              htmlFor="file-upload"
              className="flex items-center justify-center w-full border-2 border-dashed border-gray-300 hover:border-blue-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-200 p-8 rounded-xl cursor-pointer bg-white/50 backdrop-blur-sm transition-all duration-200"
            >
              <div className="text-center">
                <div className="text-4xl mb-2">📄</div>
                <p className="text-gray-700 font-medium">
                  {files ? `${files.length} file(s) selected` : "Click to upload or drag and drop"}
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  PDF, DOC, DOCX files (Max 20 files)
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* LLM Service Warning */}
        {llmStatus === "unavailable" && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-xl flex items-start">
            <span className="text-xl mr-2 mt-0.5">⚠️</span>
            <div>
              <span className="font-semibold">AI Service Unavailable</span>
              <p className="text-sm mt-1 text-yellow-700">
                Using basic keyword matching for analysis. Start Ollama with "ollama serve" for better AI-powered results.
              </p>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl flex items-center">
            <span className="text-xl mr-2">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Start Button */}
        <button
          onClick={startJob}
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-8 py-4 rounded-xl font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-500 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin h-5 w-5 mr-3 text-white" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {llmStatus === "unavailable" ? "Processing with Keywords..." : "Analyzing with AI..."}
            </span>
          ) : (
            <span className="flex items-center justify-center">
              🚀 Start Analysis
              {llmStatus === "unavailable" && (
                <span className="ml-2 text-xs bg-yellow-400 text-yellow-900 px-2 py-1 rounded-full">AI Offline</span>
              )}
            </span>
          )}
        </button>

        {/* Progress Bar */}
        {jobId && (
          <div className="mt-8 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200">
            <div className="flex items-center justify-between mb-3">
              <span className="font-semibold text-gray-700">Processing Progress</span>
              <span className="text-2xl font-bold text-blue-600">{progress.toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 h-6 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-500 to-indigo-600 h-6 rounded-full transition-all duration-500 ease-out flex items-center justify-end pr-2"
                style={{ width: `${progress}%` }}
              >
                {progress > 10 && (
                  <span className="text-white text-xs font-medium">{Math.round(progress)}%</span>
                )}
              </div>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              {progress < 100 ? (
                <span className="flex items-center">
                  {llmStatus === "unavailable" ? (
                    <>📊 Processing with keyword matching...</>
                  ) : (
                    <>🤖 Analyzing resumes with AI...</>
                  )}
                </span>
              ) : (
                <span className="flex items-center">
                  {llmStatus === "unavailable" ? (
                    <>✅ Analysis complete (basic matching)</>
                  ) : (
                    <>✅ Analysis complete!</>
                  )}
                </span>
              )}
            </p>
          </div>
        )}

        {/* Results */}
        {results.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-800">🏆 Candidate Results</h2>
              <div className="bg-blue-100 text-blue-800 px-4 py-2 rounded-full text-sm font-semibold">
                {results.length} Candidates
              </div>
            </div>

            <div className="space-y-4">
              {results.map((r, i) => (
                <div
                  key={i}
                  className="bg-white border-2 border-gray-100 rounded-xl p-6 hover:shadow-lg transition-all duration-200 hover:border-blue-200"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center space-x-4">
                      <div className="text-3xl">
                        {r.classification === "Excellent" ? "🥇" : 
                         r.classification === "Strong" ? "🥈" : 
                         r.classification === "Partial" ? "🥉" : "📋"}
                      </div>
                      <div>
                        <h3 className="font-bold text-lg text-gray-900">{r.name}</h3>
                        {r.summary && (
                          <p className="text-gray-600 text-sm mt-1">{r.summary}</p>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                        {r.score}%
                      </div>
                      <div className={`inline-block px-3 py-1 rounded-full text-xs font-semibold mt-2 ${
                        r.classification === "Excellent" ? "bg-green-100 text-green-800" :
                        r.classification === "Strong" ? "bg-blue-100 text-blue-800" :
                        r.classification === "Partial" ? "bg-yellow-100 text-yellow-800" :
                        "bg-gray-100 text-gray-800"
                      }`}>
                        {r.classification}
                      </div>
                    </div>
                  </div>

                  {/* Skill Matching Section */}
                  {(r.matched_keywords || r.match_ratio !== undefined) && (
                    <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-sm text-gray-700 flex items-center">
                          <span className="text-lg mr-2">🎯</span>
                          Skill Match Analysis
                          <span className="ml-2 text-xs text-gray-500 cursor-help" title="Shows skills from resume that match the job description">
                            ℹ️
                          </span>
                        </h4>
                        {r.match_ratio !== undefined && (
                          <span className="text-sm font-medium text-blue-600">
                            {Math.round(r.match_ratio * 100)}% Match
                          </span>
                        )}
                      </div>
                      
                      {r.matched_keywords && r.matched_keywords.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs text-gray-600 mb-2">✅ Matched Skills:</p>
                          <div className="flex flex-wrap gap-1">
                            {r.matched_keywords.slice(0, 8).map((keyword: string, idx: number) => (
                              <span
                                key={idx}
                                className="inline-block px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full font-medium"
                              >
                                {keyword}
                              </span>
                            ))}
                            {r.matched_keywords.length > 8 && (
                              <span className="inline-block px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full font-medium">
                                +{r.matched_keywords.length - 8} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {r.jd_keywords && r.jd_keywords.length > 0 && (
                        <div>
                          <p className="text-xs text-gray-600 mb-2">📋 Required Skills:</p>
                          <div className="flex flex-wrap gap-1">
                            {r.jd_keywords.slice(0, 6).map((keyword: string, idx: number) => (
                              <span
                                key={idx}
                                className={`inline-block px-2 py-1 text-xs rounded-full font-medium ${
                                  r.matched_keywords?.includes(keyword) 
                                    ? 'bg-blue-100 text-blue-800' 
                                    : 'bg-gray-100 text-gray-600'
                                }`}
                              >
                                {keyword}
                                {!r.matched_keywords?.includes(keyword) && '❌'}
                              </span>
                            ))}
                            {r.jd_keywords.length > 6 && (
                              <span className="inline-block px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full font-medium">
                                +{r.jd_keywords.length - 6} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Fallback Analysis Indicator */}
                  {r.summary?.includes('Fallback analysis') && llmStatus === 'unavailable' && (
                    <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <div className="flex items-center space-x-2 text-yellow-800">
                        <span className="text-sm">⚠️</span>
                        <span className="text-xs font-medium">Basic keyword matching (AI unavailable)</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
