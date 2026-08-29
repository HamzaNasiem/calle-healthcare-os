import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Lock, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2, ShieldCheck } from "lucide-react";
import api from "../lib/api";

// Password strength checker
const getStrength = (pw) => {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return score; // 0-4
};

const strengthLabel = ["", "Weak", "Fair", "Good", "Strong"];
const strengthColor = ["", "#ef4444", "#f59e0b", "#3b82f6", "#7FCD4D"];

const ResetPassword = () => {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);
  const [tokenValid, setTokenValid] = useState(true);

  // Supabase reset links have #access_token= in the URL fragment
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash.includes("access_token") && !hash.includes("type=recovery")) {
      // Also check for query param format
      const params = new URLSearchParams(window.location.search);
      if (!params.get("token")) {
        setTokenValid(false);
        setError("Invalid or expired reset link. Please request a new one.");
      }
    }
  }, []);

  const strength = getStrength(password);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8)
      return setError("Password must be at least 8 characters.");
    if (!/[A-Z]/.test(password))
      return setError("Password must include at least one uppercase letter.");
    if (!/[0-9]/.test(password))
      return setError("Password must include at least one number.");
    if (password !== confirm)
      return setError("Passwords do not match.");

    setLoading(true);
    try {
      // Extract token from URL hash (Supabase format)
      const hash = window.location.hash;
      const params = new URLSearchParams(hash.replace("#", "?"));
      const accessToken = params.get("access_token");

      await api.post("/auth/reset-password", {
        token: accessToken,
        new_password: password,
      });
      setDone(true);
      // Auto-redirect to login after 3 seconds
      setTimeout(() => navigate("/login"), 3000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to reset password. The link may have expired."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left — Form */}
      <div className="flex-1 flex flex-col justify-center items-center px-8 py-12 bg-surface">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-10">
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
              <p className="text-sm font-extrabold text-on-surface tracking-tight uppercase leading-none">CLINIC</p>
            </div>
          </div>

          {done ? (
            /* ---- Success State ---- */
            <div className="text-center py-6">
              <div className="flex justify-center mb-5">
                <div
                  className="w-14 h-14 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: "#7FCD4D22" }}
                >
                  <CheckCircle2 className="w-7 h-7" style={{ color: "#7FCD4D" }} />
                </div>
              </div>
              <h1 className="text-2xl font-medium text-on-surface mb-2 tracking-tight">
                Password reset!
              </h1>
              <p className="text-sm text-on-surface-variant mb-6">
                Your password has been updated successfully.
                <br />
                Redirecting you to login...
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 py-3 px-6 rounded-xl text-sm font-bold text-white transition-all"
                style={{ backgroundColor: "#396a00" }}
              >
                Go to Login
              </Link>
            </div>
          ) : (
            /* ---- Form State ---- */
            <>
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck className="w-5 h-5" style={{ color: "#7FCD4D" }} />
                <h1 className="text-[1.75rem] font-medium text-on-surface tracking-tight">
                  Set new password
                </h1>
              </div>
              <p className="text-sm text-on-surface-variant mb-8">
                Choose a strong password for your account.
              </p>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                {/* New Password */}
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-2">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type={showPw ? "text" : "password"}
                      required
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setError(null); }}
                      placeholder="Min 8 characters"
                      disabled={!tokenValid}
                      className="w-full pl-10 pr-10 py-3 bg-surface-container rounded-xl outline-none text-on-surface text-sm
                        placeholder-on-surface-variant/50 border-b-2 border-transparent focus:border-primary transition-all disabled:opacity-50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(!showPw)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60 hover:text-on-surface transition-colors"
                    >
                      {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Strength bar */}
                  {password.length > 0 && (
                    <div className="mt-2">
                      <div className="flex gap-1 mb-1">
                        {[1, 2, 3, 4].map((i) => (
                          <div
                            key={i}
                            className="h-1 flex-1 rounded-full transition-all duration-300"
                            style={{
                              backgroundColor: i <= strength ? strengthColor[strength] : "#e5e7eb",
                            }}
                          />
                        ))}
                      </div>
                      <p className="text-xs font-medium" style={{ color: strengthColor[strength] }}>
                        {strengthLabel[strength]}
                      </p>
                    </div>
                  )}

                  {/* Requirements */}
                  <div className="mt-2 space-y-1">
                    {[
                      { label: "At least 8 characters", ok: password.length >= 8 },
                      { label: "One uppercase letter", ok: /[A-Z]/.test(password) },
                      { label: "One number", ok: /[0-9]/.test(password) },
                    ].map(({ label, ok }) => (
                      <div key={label} className="flex items-center gap-1.5">
                        <div
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors"
                          style={{ backgroundColor: ok ? "#7FCD4D" : "#d1d5db" }}
                        />
                        <span className={`text-xs transition-colors ${ok ? "text-on-surface" : "text-on-surface-variant/60"}`}>
                          {label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Confirm Password */}
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-2">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type={showConfirm ? "text" : "password"}
                      required
                      value={confirm}
                      onChange={(e) => { setConfirm(e.target.value); setError(null); }}
                      placeholder="Repeat your password"
                      disabled={!tokenValid}
                      className={`w-full pl-10 pr-10 py-3 bg-surface-container rounded-xl outline-none text-on-surface text-sm
                        placeholder-on-surface-variant/50 border-b-2 transition-all disabled:opacity-50
                        ${confirm && password !== confirm ? "border-rose-400" : confirm && password === confirm ? "border-primary" : "border-transparent focus:border-primary"}`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(!showConfirm)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60 hover:text-on-surface transition-colors"
                    >
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {confirm && password !== confirm && (
                    <p className="text-xs text-rose-500 mt-1.5">Passwords do not match</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading || !tokenValid}
                  className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
                  style={{ backgroundColor: "#396a00" }}
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Updating password...
                    </>
                  ) : (
                    "Update Password"
                  )}
                </button>

                {!tokenValid && (
                  <div className="text-center mt-2">
                    <Link
                      to="/forgot-password"
                      className="text-sm font-semibold hover:opacity-80"
                      style={{ color: "#396a00" }}
                    >
                      Request a new reset link
                    </Link>
                  </div>
                )}
              </form>
            </>
          )}
        </div>
      </div>

      {/* Right — Branding panel */}
      <div
        className="hidden lg:flex w-[45%] flex-col justify-between p-12 relative overflow-hidden"
        style={{ backgroundColor: "#1a3a2e" }}
      >
        <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full opacity-20" style={{ backgroundColor: "#7FCD4D" }} />
        <div className="absolute bottom-16 -left-16 w-56 h-56 rounded-full opacity-10" style={{ backgroundColor: "#7FCD4D" }} />

        <div className="flex items-center gap-2.5 relative z-10">
          <div className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center" style={{ backgroundColor: "#7FCD4D" }}>
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

        <div className="relative z-10">
          <h2 className="text-4xl font-light text-white leading-snug mb-4">
            Secure Reset.<br />
            <span style={{ color: "#7FCD4D" }}>Your data is safe.</span>
          </h2>
          <p className="text-white/60 text-sm leading-relaxed max-w-xs">
            Your new password is encrypted end-to-end.
            Choose something strong that you haven't used before.
          </p>
        </div>

        <p className="text-white/30 text-xs relative z-10">Bytelytic OS · bytelytic.com</p>
      </div>
    </div>
  );
};

export default ResetPassword;
