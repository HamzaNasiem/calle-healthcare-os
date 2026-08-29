import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Mail, ArrowLeft, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import api from "../lib/api";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return setError("Please enter your email address.");

    setLoading(true);
    setError(null);

    try {
      await api.post("/auth/forgot-password", { email: email.trim() });
      setSent(true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Something went wrong. Please try again."
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

          {/* Back link */}
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-sm text-on-surface-variant hover:text-on-surface transition-colors mb-8"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to login
          </Link>

          {sent ? (
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
                Check your email
              </h1>
              <p className="text-sm text-on-surface-variant mb-2">
                We've sent a password reset link to
              </p>
              <p className="text-sm font-semibold text-on-surface mb-6">{email}</p>
              <p className="text-xs text-on-surface-variant mb-8 leading-relaxed">
                Didn't receive it? Check your spam folder, or{" "}
                <button
                  onClick={() => { setSent(false); setEmail(""); }}
                  className="font-semibold underline"
                  style={{ color: "#396a00" }}
                >
                  try again
                </button>.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-sm font-semibold"
                style={{ color: "#396a00" }}
              >
                <ArrowLeft className="w-4 h-4" />
                Return to login
              </Link>
            </div>
          ) : (
            /* ---- Form State ---- */
            <>
              <h1 className="text-[1.75rem] font-medium text-on-surface mb-1 tracking-tight">
                Forgot password?
              </h1>
              <p className="text-sm text-on-surface-variant mb-8 mt-1">
                No worries — we'll send you a reset link.
              </p>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
                    <input
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); setError(null); }}
                      placeholder="doctor@clinic.com"
                      className="w-full pl-10 pr-4 py-3 bg-surface-container rounded-xl outline-none text-on-surface text-sm
                        placeholder-on-surface-variant/50 border-b-2 border-transparent focus:border-primary transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  style={{ backgroundColor: "#396a00" }}
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Sending reset link...
                    </>
                  ) : (
                    "Send Reset Link"
                  )}
                </button>

                <div className="text-center mt-4">
                  <span className="text-sm text-on-surface-variant">Remember it? </span>
                  <Link
                    to="/login"
                    className="text-sm font-bold hover:opacity-80 transition-opacity"
                    style={{ color: "#396a00" }}
                  >
                    Sign in
                  </Link>
                </div>
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
            Account Recovery.<br />
            <span style={{ color: "#7FCD4D" }}>Quick & Secure.</span>
          </h2>
          <p className="text-white/60 text-sm leading-relaxed max-w-xs">
            A password reset link will be sent to your registered email.
            The link expires in 1 hour for your security.
          </p>
          <div className="mt-8 space-y-3">
            {["Reset link sent instantly", "Link expires in 1 hour", "No data loss during reset"].map((feat) => (
              <div key={feat} className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: "#7FCD4D" }} />
                <span className="text-white/70 text-sm">{feat}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-white/30 text-xs relative z-10">Bytelytic OS · bytelytic.com</p>
      </div>
    </div>
  );
};

export default ForgotPassword;
