import React, { useEffect, useState } from "react";
import { format, parseISO } from "date-fns";
import api from "../lib/api";

const STATUS_DOT = {
  scheduled: "bg-amber-400",
  confirmed: "bg-primary",
  cancelled: "bg-rose-400",
  completed: "bg-blue-400",
  no_show: "bg-slate-400",
};

const STATUS_LABEL = {
  scheduled: "text-amber-600",
  confirmed: "text-primary",
  cancelled: "text-rose-500",
  completed: "text-blue-600",
  no_show: "text-slate-500",
};

const AppointmentTable = () => {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTodayAppointments = async () => {
      try {
        const res = await api.get("/appointments/today");
        setAppointments(res.data.data || []);
      } catch (err) {
        console.error("Failed to fetch today's appointments", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTodayAppointments();
  }, []);

  const initials = (name) =>
    (name || "?")
      .split(" ")
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

  return (
    <div className="bg-white rounded-2xl shadow-card overflow-hidden">
      <div className="px-6 py-5 flex justify-between items-center">
        <div>
          <h3 className="font-bold text-on-surface text-base">Up Next</h3>
          <div className="w-6 h-0.5 bg-primary mt-1" />
        </div>
        <a
          href="/appointments"
          className="text-xs font-semibold text-primary hover:text-primary/80 transition-colors"
        >
          View All →
        </a>
      </div>

      {loading ? (
        <div className="px-6 pb-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-14 bg-surface-container rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : appointments.length === 0 ? (
        <div className="px-6 pb-8 pt-2 text-center">
          <div className="w-10 h-10 bg-surface-container rounded-full flex items-center justify-center mx-auto mb-3">
            <svg
              className="w-5 h-5 text-on-surface-variant"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <p className="text-on-surface-variant text-sm font-medium">
            No appointments today
          </p>
          <p className="text-on-surface-variant/60 text-xs mt-1">
            The AI will fill this when patients call
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container">
                <th className="px-6 py-3 section-label">Patient</th>
                <th className="px-6 py-3 section-label">Type</th>
                <th className="px-6 py-3 section-label">Time</th>
                <th className="px-6 py-3 section-label">Status</th>
                <th className="px-6 py-3 section-label">Booked By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {appointments.map((appt) => (
                <tr
                  key={appt.id}
                  className="hover:bg-surface transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs flex-shrink-0">
                        {initials(appt.patient_name)}
                      </div>
                      <div>
                        <div className="font-semibold text-on-surface text-sm">
                          {appt.patient_name}
                        </div>
                        <div className="text-xs text-on-surface-variant">
                          {appt.patient_phone}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-on-surface-variant font-medium">
                    {appt.appointment_type}
                  </td>
                  <td className="px-6 py-4 text-sm text-on-surface">
                    {appt.datetime
                      ? format(parseISO(appt.datetime), "h:mm a")
                      : "—"}
                    <span className="text-xs text-on-surface-variant ml-1">
                      ({appt.duration_minutes}m)
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[appt.status] || STATUS_DOT.scheduled}`}
                      />
                      <span
                        className={`text-xs font-semibold capitalize ${STATUS_LABEL[appt.status] || STATUS_LABEL.scheduled}`}
                      >
                        {appt.status?.replace("_", " ")}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`text-xs font-semibold px-2 py-1 rounded-full ${
                        appt.booked_by === "ai"
                          ? "bg-primary/10 text-primary"
                          : "bg-surface-container text-on-surface-variant"
                      }`}
                    >
                      {appt.booked_by === "ai" ? "AI" : "Staff"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AppointmentTable;
