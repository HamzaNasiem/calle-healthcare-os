import React from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

const RevenueCard = ({
  title,
  amount,
  percentage,
  isPositive,
  icon: Icon,
  hero = false,
  color = "primary",
}) => {
  const colorMap = {
    primary: { bg: "bg-primary/10", text: "text-primary" },
    amber: { bg: "bg-amber-100", text: "text-amber-600" },
    blue: { bg: "bg-blue-100", text: "text-blue-600" },
    rose: { bg: "bg-rose-100", text: "text-rose-600" },
    violet: { bg: "bg-violet-100", text: "text-violet-600" },
    teal: { bg: "bg-teal-100", text: "text-teal-600" },
  };
  const { bg, text } = colorMap[color] || colorMap.primary;

  if (hero) {
    return (
      <div
        className="rounded-2xl p-6 flex flex-col h-full relative overflow-hidden"
        style={{ backgroundColor: "#1a3a2e" }}
      >
        <div
          className="absolute -top-8 -right-8 w-36 h-36 rounded-full opacity-20"
          style={{ backgroundColor: "#7FCD4D" }}
        />
        <div className="relative z-10 flex flex-col h-full">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
            style={{ backgroundColor: "rgba(127,205,77,0.2)" }}
          >
            <Icon className="w-5 h-5" style={{ color: "#7FCD4D" }} />
          </div>
          <h3 className="text-white/60 font-medium text-sm mb-2">{title}</h3>
          <div className="text-5xl font-light text-white tracking-tight mt-auto">
            {amount}
          </div>
          <div className="flex items-center gap-2 mt-3">
            <div
              className={`flex items-center text-xs font-semibold px-2 py-1 rounded-full ${
                isPositive
                  ? "bg-sidebar-active/20 text-sidebar-active"
                  : "bg-rose-500/20 text-rose-300"
              }`}
            >
              {isPositive ? (
                <ArrowUpRight className="w-3 h-3 mr-0.5" />
              ) : (
                <ArrowDownRight className="w-3 h-3 mr-0.5" />
              )}
              {percentage}%
            </div>
            <span className="text-white/30 text-xs">vs last month</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-5 shadow-card flex flex-col h-full hover:shadow-premium hover:-translate-y-0.5 transition-all duration-200">
      <div
        className={`w-11 h-11 rounded-xl ${bg} flex items-center justify-center ${text} mb-4`}
      >
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="text-on-surface-variant font-medium text-sm mb-1">
        {title}
      </h3>
      <div className="flex items-end justify-between mt-auto pt-2">
        <div className="text-2xl font-bold text-on-surface">{amount}</div>
        {percentage !== undefined && (
          <div
            className={`flex items-center text-xs font-semibold px-2 py-1 rounded-full ${
              isPositive
                ? "bg-primary/10 text-primary"
                : "bg-rose-50 text-rose-500"
            }`}
          >
            {isPositive ? (
              <ArrowUpRight className="w-3 h-3 mr-0.5" />
            ) : (
              <ArrowDownRight className="w-3 h-3 mr-0.5" />
            )}
            {percentage}%
          </div>
        )}
      </div>
    </div>
  );
};

export default RevenueCard;
