import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { 
  Mail, Lock, ArrowRight, AlertCircle, 
  Building2, User, Clock, CalendarDays, CheckCircle2, Loader2, Shield
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

const TIMEZONES = [
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Asia/Dubai", "Asia/Kolkata", "Asia/Tokyo", "Australia/Sydney"
];

const DEFAULT_HOURS = {
  mon: "08:00-17:00", tue: "08:00-17:00", wed: "08:00-17:00", 
  thu: "08:00-17:00", fri: "08:00-17:00", sat: "closed", sun: "closed"
};

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Google OAuth & Onboarding States
  const [config, setConfig] = useState(null);
  const [googleUser, setGoogleUser] = useState(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(1);
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [onboardingError, setOnboardingError] = useState(null);
  const [onboardingData, setOnboardingData] = useState({
    clinicName: "", specialty: "", city: "", timezone: "America/Chicago",
    doctorName: "", doctorCredentials: "", doctorPhone: "",
    businessHours: { ...DEFAULT_HOURS },
    appointmentTypes: [
      { name: "Initial Consultation", duration: 60, duration_minutes: 60, fee: 150 },
      { name: "Follow-up Visit", duration: 30, duration_minutes: 30, fee: 75 }
    ]
  });

  // MFA States
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaData, setMfaData] = useState(null);
  const [otpCode, setOtpCode] = useState("");
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaError, setMfaError] = useState(null);

  // Fetch Supabase URL & Anon Key dynamically
  useEffect(() => {
    api.get("/auth/config")
      .then(res => setConfig(res.data))
      .catch(err => console.error("Failed to load auth config", err));
  }, []);

  // Detect Supabase OAuth Hash redirect
  useEffect(() => {
    const handleHashAuth = async () => {
      const hash = window.location.hash;
      if (!hash || !hash.includes("access_token")) return;

      setLoading(true);
      setError(null);
      
      try {
        const params = new URLSearchParams(hash.replace("#", "?"));
        const token = params.get("access_token");
        const refreshToken = params.get("refresh_token");

        if (!token) return;

        // Clean URL hash
        window.history.replaceState(null, null, window.location.pathname);

        // Fetch profile using this token
        const meRes = await api.get("/auth/me", {
          headers: { Authorization: `Bearer ${token}` }
        });

        const { clinicId, clinicName, timezone, role, email: userEmail, userId } = meRes.data;

        if (clinicId) {
          // Clinic exists — login instantly
          login({
            token,
            refreshToken,
            clinicId,
            clinicName,
            timezone,
            role,
            email: userEmail,
            userId,
            rememberMe: true
          });
          navigate("/");
        } else {
          // Google user needs onboarding setup
          setGoogleUser({ token, refreshToken, email: userEmail, userId });
          setShowOnboarding(true);
        }
      } catch (err) {
        console.error("Google login failed", err);
        setError("Failed to authenticate with Google. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    handleHashAuth();
  }, [navigate, login]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await api.post("/auth/login", { email, password });
      
      if (response.data.mfaRequired) {
        setMfaRequired(true);
        setMfaData(response.data);
        setLoading(false);
        return;
      }

      const token = response.data.token || response.data.access_token;
      const refreshToken = response.data.refreshToken || response.data.refresh_token;
      const clinicId = response.data.clinicId || response.data.clinic_id || "d3b07384-d113-46a6-a719-38cf89235d54";
      const clinicName = response.data.clinicName || response.data.clinic_name || "Sunrise Medical Clinic";
      const timezone = response.data.timezone || "America/Chicago";
      const role = response.data.role || "owner";
      const userEmail = response.data.userEmail || response.data.email || email;
      const userId = response.data.userId || response.data.id || "demo-user-001";

      login({ token, refreshToken, clinicId, clinicName, timezone, role, email: userEmail, userId, rememberMe });
      navigate("/");

    } catch (err) {
      setError(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          "Failed to login. Please check credentials.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleMfaVerify = async (e) => {
    e.preventDefault();
    if (otpCode.length !== 6) {
      setMfaError("Please enter a valid 6-digit code.");
      return;
    }
    setMfaLoading(true);
    setMfaError(null);

    try {
      const response = await api.post(
        "/auth/mfa/verify",
        { factor_id: mfaData.factorId, code: otpCode },
        { headers: { Authorization: `Bearer ${mfaData.tempToken}` } }
      );
      
      const token = response.data.access_token || response.data.token;
      const refreshToken = response.data.refresh_token || response.data.refreshToken;
      const clinicId = mfaData.clinicId || mfaData.clinic_id || "d3b07384-d113-46a6-a719-38cf89235d54";
      const clinicName = mfaData.clinicName || mfaData.clinic_name || "Sunrise Medical Clinic";
      const timezone = mfaData.timezone || "America/Chicago";
      const role = mfaData.role || "owner";
      const userEmail = mfaData.userEmail || mfaData.email || email;
      const userId = mfaData.userId || mfaData.id || "demo-user-001";

      login({
        token,
        refreshToken,
        clinicId,
        clinicName,
        timezone,
        role,
        email: userEmail,
        userId,
        rememberMe
      });
      navigate("/");
    } catch (err) {
      setMfaError(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          "Invalid authentication code. Please try again."
      );
    } finally {
      setMfaLoading(false);
    }
  };

  // Google Onboarding Form Handlers
  const updateOnboarding = (key, value) => {
    setOnboardingData(prev => ({ ...prev, [key]: value }));
    if (onboardingError) setOnboardingError(null);
  };

  const handleOnboardingSubmit = async () => {
    setOnboardingLoading(true);
    setOnboardingError(null);
    try {
      const res = await api.post("/auth/google-onboarding", onboardingData, {
        headers: { Authorization: `Bearer ${googleUser.token}` }
      });
      const { token, clinicId, clinicName, timezone, role, userEmail, userId } = res.data;
      
      login({
        token,
        refreshToken: googleUser.refreshToken,
        clinicId,
        clinicName,
        timezone,
        role,
        email: userEmail,
        userId,
        rememberMe: true
      });
      setShowOnboarding(false);
      navigate("/");
    } catch (err) {
      setOnboardingError(err.response?.data?.detail || err.response?.data?.error || "Onboarding failed. Please try again.");
    } finally {
      setOnboardingLoading(false);
    }
  };

  const nextOnboardingStep = () => {
    if (onboardingStep === 1) {
      const nameStr = onboardingData.clinicName.trim().toLowerCase();
      const hasLetters = /[a-zA-Z]/.test(nameStr);
      if (!nameStr || nameStr.length < 3 || nameStr === "string" || nameStr === "test" || !hasLetters) {
        return setOnboardingError("Please enter a valid Clinic Name (min 3 characters, must contain letters).");
      }
    }
    if (onboardingStep === 2) {
      if (!onboardingData.doctorName) return setOnboardingError("Primary Doctor Name is required.");
    }
    setOnboardingError(null);
    setOnboardingStep(s => Math.min(s + 1, 4));
  };

  const prevOnboardingStep = () => {
    setOnboardingError(null);
    setOnboardingStep(s => Math.max(s - 1, 1));
  };

  return (
    <div className="min-h-screen flex">
      {/* Left — Form */}
      <div className="flex-1 flex flex-col justify-center items-center px-8 py-12 bg-surface">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-8">
            <div
              className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: "#7FCD4D" }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e"/>
                <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-extrabold text-on-surface tracking-tight uppercase leading-none">BYTELYTIC</p>
              <p className="text-sm font-extrabold text-on-surface tracking-tight uppercase leading-none mt-0.5">CLINIC</p>
            </div>
          </div>          {mfaRequired ? (
            <>
              {/* Heading */}
              <h1 className="text-[1.75rem] font-medium text-on-surface mb-1 tracking-tight flex items-center gap-2">
                <Shield className="w-7 h-7 text-primary animate-pulse" /> Two-Factor Code
              </h1>
              <p className="text-sm text-on-surface-variant mb-6 mt-1">
                Enter verification code from your authenticator app.
              </p>

              <form className="space-y-4" onSubmit={handleMfaVerify}>
                {mfaError && (
                  <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{mfaError}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    6-Digit Verification Code
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      maxLength={6}
                      autoFocus
                      required
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                      placeholder="000 000"
                      className="w-full pl-10 pr-4 py-3 bg-surface-container rounded-xl outline-none text-on-surface text-lg font-bold tracking-[0.4em] text-center
                        placeholder-on-surface-variant/30 border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={mfaLoading}
                  className="group w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
                  style={{ backgroundColor: "#396a00" }}
                >
                  {mfaLoading ? "Verifying..." : "Verify Code"}
                  {!mfaLoading && (
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  )}
                </button>

                <div className="text-center mt-6">
                  <button
                    type="button"
                    onClick={() => {
                      setMfaRequired(false);
                      setMfaData(null);
                      setOtpCode("");
                      setMfaError(null);
                    }}
                    className="text-sm font-bold text-primary hover:text-primary/80 transition-colors"
                  >
                    Back to sign in
                  </button>
                </div>
              </form>
            </>
          ) : (
            <>
              {/* Heading */}
              <h1 className="text-[1.75rem] font-medium text-on-surface mb-1 tracking-tight">
                Welcome back
              </h1>
              <p className="text-sm text-on-surface-variant mb-6 mt-1">
                Sign in to your clinic dashboard
              </p>

              <form className="space-y-4" onSubmit={handleLogin}>
                {error && (
                  <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="doctor@clinic.com"
                      className="w-full pl-10 pr-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm
                        placeholder-on-surface-variant/50 border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full pl-10 pr-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm
                        placeholder-on-surface-variant/50 border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="w-4 h-4 rounded accent-primary cursor-pointer"
                    />
                    <span className="text-sm text-on-surface-variant">
                      Remember me
                    </span>
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-sm font-semibold text-primary hover:text-primary/80 transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="group w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
                  style={{ backgroundColor: "#396a00" }}
                >
                  {loading ? "Signing in..." : "Sign In"}
                  {!loading && (
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  )}
                </button>

                {import.meta.env.VITE_DEDICATED_CLINIC_MODE !== 'true' && (
                  <div className="text-center mt-6">
                    <span className="text-sm text-on-surface-variant">Don't have an account? </span>
                    <a href="/signup" className="text-sm font-bold text-primary hover:text-primary/80 transition-colors">Sign up</a>
                  </div>
                )}
              </form>
            </>
          )}
        </div>
      </div>

      {/* Right — Branding panel (hidden on mobile) */}
      <div
        className="hidden lg:flex w-[45%] flex-col justify-between p-12 relative overflow-hidden"
        style={{ backgroundColor: "#1a3a2e" }}
      >
        {/* Decorative circles */}
        <div
          className="absolute -top-24 -right-24 w-72 h-72 rounded-full opacity-20"
          style={{ backgroundColor: "#7FCD4D" }}
        />
        <div
          className="absolute bottom-16 -left-16 w-56 h-56 rounded-full opacity-10"
          style={{ backgroundColor: "#7FCD4D" }}
        />

        {/* Top logo */}
        <div className="flex items-center gap-2.5 relative z-10">
          <div
            className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center"
            style={{ backgroundColor: "#7FCD4D" }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e"/>
              <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e"/>
            </svg>
          </div>
          <div>
            <p className="text-white font-extrabold text-sm uppercase leading-none">BYTELYTIC</p>
            <p className="text-white font-extrabold text-sm uppercase leading-none mt-0.5">CLINIC</p>
          </div>
        </div>

        {/* Center copy */}
        <div className="relative z-10">
          <h2 className="text-4xl font-light text-white leading-snug mb-4">
            Your AI Front Desk.
            <br />
            <span style={{ color: "#7FCD4D" }}>Always On.</span>
          </h2>
          <p className="text-white/60 text-sm leading-relaxed max-w-xs">
            Automated appointment booking, 24/7 patient calls, and revenue
            recovery — all handled by AI while you focus on care.
          </p>

          <div className="mt-8 space-y-3">
            {[
              "Answers every call, 24/7",
              "Books appointments automatically",
              "Sends reminders & follow-ups",
            ].map((feat) => (
              <div key={feat} className="flex items-center gap-3">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: "#7FCD4D" }}
                />
                <span className="text-white/70 text-sm">{feat}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom tagline */}
        <p className="text-white/30 text-xs relative z-10">
          Bytelytic OS · bytelytic.com
        </p>
      </div>

      {/* Google Setup/Onboarding Modal Dialog */}
      {showOnboarding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-surface border border-on-surface-variant/10 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-scaleUp flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="p-6 border-b border-on-surface-variant/10 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-on-surface">Complete Clinic Setup</h3>
                <p className="text-xs text-on-surface-variant/80 mt-1">Set up your AI receptionist to complete your signup.</p>
              </div>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 4].map(num => (
                  <div 
                    key={num} 
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                      onboardingStep >= num ? "text-white bg-primary" : "bg-surface-container text-on-surface-variant"
                    }`}
                  >
                    {num}
                  </div>
                ))}
              </div>
            </div>

            {/* Error Message */}
            {onboardingError && (
              <div className="mx-6 mt-4 p-3.5 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{onboardingError}</span>
              </div>
            )}

            {/* Step Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-4">
              {onboardingStep === 1 && (
                <div className="space-y-4 animate-fadeIn">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Clinic Name</label>
                    <input 
                      type="text" 
                      value={onboardingData.clinicName} 
                      onChange={(e) => updateOnboarding("clinicName", e.target.value)} 
                      placeholder="Apex Wellness Center" 
                      className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Specialty</label>
                      <input 
                        type="text" 
                        value={onboardingData.specialty} 
                        onChange={(e) => updateOnboarding("specialty", e.target.value)} 
                        placeholder="e.g. Dentistry" 
                        className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">City</label>
                      <input 
                        type="text" 
                        value={onboardingData.city} 
                        onChange={(e) => updateOnboarding("city", e.target.value)} 
                        placeholder="e.g. New York" 
                        className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Timezone</label>
                    <select 
                      value={onboardingData.timezone} 
                      onChange={(e) => updateOnboarding("timezone", e.target.value)}
                      className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                    >
                      {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                    </select>
                  </div>
                </div>
              )}

              {onboardingStep === 2 && (
                <div className="space-y-4 animate-fadeIn">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Primary Doctor Name</label>
                    <input 
                      type="text" 
                      value={onboardingData.doctorName} 
                      onChange={(e) => updateOnboarding("doctorName", e.target.value)} 
                      placeholder="Dr. Sarah Jenkins" 
                      className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Credentials</label>
                      <input 
                        type="text" 
                        value={onboardingData.doctorCredentials} 
                        onChange={(e) => updateOnboarding("doctorCredentials", e.target.value)} 
                        placeholder="e.g. DDS, MD" 
                        className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">Doctor Phone</label>
                      <input 
                        type="text" 
                        value={onboardingData.doctorPhone} 
                        onChange={(e) => updateOnboarding("doctorPhone", e.target.value)} 
                        placeholder="+1 (555) 000-0000" 
                        className="w-full px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all"
                      />
                    </div>
                  </div>
                </div>
              )}

              {onboardingStep === 3 && (
                <div className="space-y-2 animate-fadeIn max-h-[40vh] overflow-y-auto pr-1">
                  {Object.keys(DEFAULT_HOURS).map(day => {
                    const isOpen = onboardingData.businessHours[day] !== "closed";
                    const [start, end] = isOpen ? onboardingData.businessHours[day].split("-") : ["08:00", "17:00"];
                    
                    return (
                      <div key={day} className="flex items-center justify-between p-3 bg-surface-container rounded-xl">
                        <div className="flex items-center gap-3 w-1/3">
                          <input 
                            type="checkbox" 
                            checked={isOpen}
                            onChange={(e) => {
                              const newHours = { ...onboardingData.businessHours };
                              newHours[day] = e.target.checked ? "08:00-17:00" : "closed";
                              updateOnboarding("businessHours", newHours);
                            }}
                            className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary"
                          />
                          <span className="text-sm font-semibold text-on-surface capitalize">{day}</span>
                        </div>
                        
                        {isOpen ? (
                          <div className="flex items-center gap-2">
                            <input type="time" value={start} onChange={e => {
                              const newHours = { ...onboardingData.businessHours };
                              newHours[day] = `${e.target.value}-${end}`;
                              updateOnboarding("businessHours", newHours);
                            }} className="bg-surface rounded border border-transparent px-2 py-1 text-xs text-on-surface outline-none focus:border-primary" />
                            <span className="text-on-surface-variant text-[10px] uppercase">to</span>
                            <input type="time" value={end} onChange={e => {
                              const newHours = { ...onboardingData.businessHours };
                              newHours[day] = `${start}-${e.target.value}`;
                              updateOnboarding("businessHours", newHours);
                            }} className="bg-surface rounded border border-transparent px-2 py-1 text-xs text-on-surface outline-none focus:border-primary" />
                          </div>
                        ) : (
                          <span className="text-xs text-on-surface-variant font-medium px-4">Closed</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {onboardingStep === 4 && (
                <div className="space-y-3 animate-fadeIn max-h-[40vh] overflow-y-auto pr-1">
                  {onboardingData.appointmentTypes.map((type, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input 
                        type="text"
                        value={type.name} 
                        onChange={(e) => {
                          const newTypes = [...onboardingData.appointmentTypes];
                          newTypes[idx].name = e.target.value;
                          updateOnboarding("appointmentTypes", newTypes);
                        }} 
                        placeholder="Service Name" 
                        className="flex-1 px-4 py-2.5 bg-surface-container rounded-xl outline-none text-on-surface text-sm border-b-2 border-transparent focus:border-primary transition-all" 
                      />
                      
                      <div className="flex items-center gap-1 bg-surface-container rounded-xl px-2">
                        <input type="number" value={type.duration || type.duration_minutes || 30} onChange={(e) => {
                          const newTypes = [...onboardingData.appointmentTypes];
                          const val = parseInt(e.target.value) || 30;
                          newTypes[idx].duration = val;
                          newTypes[idx].duration_minutes = val;
                          updateOnboarding("appointmentTypes", newTypes);
                        }} className="w-12 bg-transparent text-sm py-2.5 outline-none text-center" />
                        <span className="text-xs text-on-surface-variant pr-2">min</span>
                      </div>

                      <div className="flex items-center gap-1 bg-surface-container rounded-xl px-2">
                        <span className="text-xs text-on-surface-variant pl-1">$</span>
                        <input type="number" value={type.fee !== undefined ? type.fee : 100} onChange={(e) => {
                          const newTypes = [...onboardingData.appointmentTypes];
                          newTypes[idx].fee = parseFloat(e.target.value) || 0;
                          updateOnboarding("appointmentTypes", newTypes);
                        }} className="w-14 bg-transparent text-sm py-2.5 outline-none text-center" />
                      </div>
                      
                      <button onClick={() => {
                        const newTypes = onboardingData.appointmentTypes.filter((_, i) => i !== idx);
                        updateOnboarding("appointmentTypes", newTypes);
                      }} className="p-2.5 text-on-surface-variant hover:text-rose-500 transition-colors rounded-xl">
                        ✕
                      </button>
                    </div>
                  ))}
                  
                  <button onClick={() => {
                    updateOnboarding("appointmentTypes", [...onboardingData.appointmentTypes, { name: "", duration: 30, duration_minutes: 30, fee: 100 }]);
                  }} className="w-full py-3 mt-2 border border-dashed border-on-surface-variant/20 text-on-surface-variant text-sm font-semibold rounded-xl hover:border-primary hover:text-primary transition-colors">
                    + Add Service
                  </button>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="p-6 border-t border-on-surface-variant/10 flex items-center justify-between bg-surface-container/20">
              <button 
                onClick={onboardingStep > 1 ? prevOnboardingStep : () => setShowOnboarding(false)}
                disabled={onboardingLoading}
                className="text-sm font-semibold text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-50"
              >
                {onboardingStep > 1 ? "Back" : "Cancel"}
              </button>
              
              {onboardingStep < 4 ? (
                <button 
                  onClick={nextOnboardingStep}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold text-white transition-all hover:opacity-90"
                  style={{ backgroundColor: "#396a00" }}
                >
                  Next <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button 
                  onClick={handleOnboardingSubmit}
                  disabled={onboardingLoading}
                  className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60"
                  style={{ backgroundColor: "#396a00" }}
                >
                  {onboardingLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  {onboardingLoading ? "Provisioning..." : "Complete Setup"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Login;

