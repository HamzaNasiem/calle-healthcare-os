import React, { useState, useEffect, useMemo } from "react";
import {
  Users,
  UserPlus,
  Trash2,
  Shield,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  Search,
  Mail,
  User,
  Stethoscope,
  Headphones,
  Eye,
  Lock,
  Check
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

const ROLE_CONFIGS = {
  owner: {
    label: "Owner / Co-Owner",
    shortLabel: "Owner",
    icon: Shield,
    badgeBg: "bg-[#edf7e0] text-[#396a00] border-[#d2ebbc]",
    description: "Full access to dashboard, patient charts, staff management & billing."
  },
  clinician: {
    label: "Clinician / Doctor",
    shortLabel: "Clinician",
    icon: Stethoscope,
    badgeBg: "bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd]",
    description: "Clinical access to appointments, patient records, and medical notes."
  },
  doctor: {
    label: "Clinician / Doctor",
    shortLabel: "Clinician",
    icon: Stethoscope,
    badgeBg: "bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd]",
    description: "Clinical access to appointments, patient records, and medical notes."
  },
  staff: {
    label: "Staff / Front Desk",
    shortLabel: "Staff",
    icon: Headphones,
    badgeBg: "bg-[#fef3c7] text-[#b45309] border-[#fde68a]",
    description: "Manage appointment bookings, patient schedules, and live call logs."
  },
  front_desk: {
    label: "Staff / Front Desk",
    shortLabel: "Staff",
    icon: Headphones,
    badgeBg: "bg-[#fef3c7] text-[#b45309] border-[#fde68a]",
    description: "Manage appointment bookings, patient schedules, and live call logs."
  },
  viewer: {
    label: "Viewer / Read Only",
    shortLabel: "Viewer",
    icon: Eye,
    badgeBg: "bg-[#f1f5f9] text-[#475569] border-[#e2e8f0]",
    description: "View-only access to calendar, patient list, and analytics reports."
  },
  read_only: {
    label: "Viewer / Read Only",
    shortLabel: "Viewer",
    icon: Eye,
    badgeBg: "bg-[#f1f5f9] text-[#475569] border-[#e2e8f0]",
    description: "View-only access to calendar, patient list, and analytics reports."
  }
};

const PRIMARY_ROLES = ["owner", "clinician", "staff", "viewer"];

const FILTER_OPTIONS = [
  { id: "all", label: "All Roles", roles: [] },
  { id: "owner", label: "Owners", roles: ["owner"] },
  { id: "clinician", label: "Clinicians", roles: ["clinician", "doctor"] },
  { id: "staff", label: "Staff", roles: ["staff", "front_desk"] },
  { id: "viewer", label: "Viewers", roles: ["viewer", "read_only"] }
];

const TeamSettings = () => {
  const { user: currentUser } = useAuth();
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRole, setFilterRole] = useState("all");

  // Invite Modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("staff");
  const [inviting, setInviting] = useState(false);

  // Action states
  const [updatingUserId, setUpdatingUserId] = useState(null);
  const [removingUserId, setRemovingUserId] = useState(null);
  const [deleteConfirmMember, setDeleteConfirmMember] = useState(null);

  useEffect(() => {
    fetchStaff();
  }, []);

  const showNotification = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => {
      setMsg(prev => (prev?.text === text ? null : prev));
    }, 5000);
  };

  const fetchStaff = async () => {
    try {
      setLoading(true);
      const res = await api.get("/staff");
      setStaff(res.data?.data || []);
    } catch (err) {
      console.error("[TeamSettings.fetchStaff] Error:", err);
      const errorMsg = err.response?.data?.error || err.response?.data?.detail || "Failed to load team members. Please refresh the page.";
      showNotification("error", errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !inviteName.trim()) {
      showNotification("error", "Please fill in all required fields.");
      return;
    }

    setInviting(true);
    try {
      const res = await api.post("/staff/invite", {
        email: inviteEmail.trim().toLowerCase(),
        name: inviteName.trim(),
        role: inviteRole
      });

      showNotification("success", res.data?.message || "Team member invited successfully! Temporary credentials sent.");
      setIsInviteModalOpen(false);
      setInviteEmail("");
      setInviteName("");
      setInviteRole("front_desk");
      await fetchStaff();
    } catch (err) {
      console.error("[TeamSettings.handleInvite] Error:", err);
      const errorMsg = err.response?.data?.error || err.response?.data?.detail || "Failed to invite member. Please check details.";
      showNotification("error", errorMsg);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (member, newRole) => {
    if (member.role === newRole) return;

    const targetId = member.user_id || member.id;
    const isSelf =
      member.user_id === currentUser?.id ||
      member.id === currentUser?.id ||
      (member.email && currentUser?.email && member.email.toLowerCase() === currentUser.email.toLowerCase()) ||
      (member.role === "owner" && member.is_owner);

    if (isSelf && newRole !== "owner") {
      showNotification("error", "You cannot remove the Owner role from your own account.");
      return;
    }

    setUpdatingUserId(targetId);
    try {
      await api.put(`/staff/${targetId}/role`, { role: newRole });
      
      // Optimistic update
      setStaff(prev =>
        prev.map(m => ((m.user_id === targetId || m.id === targetId) ? { ...m, role: newRole } : m))
      );
      showNotification("success", `Updated role for ${member.name} to ${ROLE_CONFIGS[newRole]?.label || newRole}.`);
    } catch (err) {
      console.error("[TeamSettings.handleRoleChange] Error:", err);
      const errorMsg = err.response?.data?.error || err.response?.data?.detail || "Failed to update role.";
      showNotification("error", errorMsg);
      await fetchStaff(); // Revert
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleConfirmRemove = async () => {
    if (!deleteConfirmMember) return;
    const member = deleteConfirmMember;
    const targetId = member.user_id || member.id;
    setRemovingUserId(targetId);
    try {
      await api.delete(`/staff/${targetId}`);
      showNotification("success", `${member.name} has been removed from the team.`);
      setStaff(prev => prev.filter(m => m.user_id !== targetId && m.id !== targetId));
      setDeleteConfirmMember(null);
    } catch (err) {
      console.error("[TeamSettings.handleConfirmRemove] Error:", err);
      const errorMsg = err.response?.data?.error || err.response?.data?.detail || "Failed to remove member.";
      showNotification("error", errorMsg);
    } finally {
      setRemovingUserId(null);
    }
  };

  // Filtered staff list
  const filteredStaff = useMemo(() => {
    return staff.filter(member => {
      const matchesSearch =
        member.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        member.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        member.role?.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesRole = filterRole === "all" || member.role === filterRole;

      return matchesSearch && matchesRole;
    });
  }, [staff, searchQuery, filterRole]);

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="border-b border-surface-container pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-on-surface">Team & Staff Access</h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
              {staff.length} {staff.length === 1 ? "member" : "members"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant mt-1">
            Manage who has access to your clinic's workspace, role permissions, and administrative controls.
          </p>
        </div>
        <button
          onClick={() => setIsInviteModalOpen(true)}
          className="btn-primary py-2 px-4 text-sm flex items-center justify-center gap-2 shadow-sm shrink-0"
        >
          <UserPlus className="w-4 h-4" />
          <span>Invite Team Member</span>
        </button>
      </div>

      {/* Notification Toast */}
      {msg && (
        <div
          className={`px-4 py-3 rounded-xl text-sm font-medium flex items-center justify-between gap-3 border shadow-sm transition-all ${
            msg.type === "success"
              ? "bg-[#edf7e0] text-[#396a00] border-[#d2ebbc]"
              : "bg-[#fce4ec] text-[#b71c1c] border-[#f8bbd0]"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {msg.type === "success" ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
            )}
            <span>{msg.text}</span>
          </div>
          <button
            onClick={() => setMsg(null)}
            className="text-current opacity-70 hover:opacity-100 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none" />
          <input
            type="text"
            placeholder="Search by name, email, or role..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="input-field pl-10 pr-4 py-2 text-sm w-full"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-xs font-semibold text-on-surface-variant whitespace-nowrap">Filter:</span>
          {["all", "owner", "doctor", "front_desk", "read_only"].map(r => (
            <button
              key={r}
              onClick={() => setFilterRole(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                filterRole === r
                  ? "bg-primary text-on-primary font-semibold shadow-xs"
                  : "bg-surface-container-lowest border border-surface-container text-on-surface-variant hover:bg-surface-container"
              }`}
            >
              {r === "all" ? "All Roles" : ROLE_CONFIGS[r]?.shortLabel || r}
            </button>
          ))}
        </div>
      </div>

      {/* Staff List Table / Cards */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-xs text-on-surface-variant">Loading clinic team members...</p>
        </div>
      ) : (
        <div className="bg-surface-container-lowest border border-surface-container rounded-2xl overflow-hidden shadow-xs divide-y divide-surface-container">
          {filteredStaff.map((member) => {
            const roleConfig = ROLE_CONFIGS[member.role] || ROLE_CONFIGS.front_desk;
            const RoleIcon = roleConfig.icon;
            const targetId = member.user_id || member.id;
            const isSelf =
              member.user_id === currentUser?.id ||
              member.id === currentUser?.id ||
              (member.email && currentUser?.email && member.email.toLowerCase() === currentUser.email.toLowerCase()) ||
              (member.role === "owner" && member.is_owner) ||
              (member.is_owner === true && staff.length === 1);
            const isUpdating = updatingUserId === targetId;

            return (
              <div
                key={member.id || member.user_id}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface-container/20 transition-colors"
              >
                {/* User Info */}
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-surface-container flex items-center justify-center flex-shrink-0 text-on-surface-variant border border-surface-container">
                    <User className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-bold text-on-surface truncate">
                        {member.name}
                      </p>
                      {isSelf && (
                        <span className="text-[11px] font-semibold px-2 py-0.5 bg-primary/10 text-primary rounded-full border border-primary/20">
                          You
                        </span>
                      )}
                      <span
                        className={`text-[11px] font-medium px-2 py-0.5 rounded-md border flex items-center gap-1 ${roleConfig.badgeBg}`}
                      >
                        <RoleIcon className="w-3 h-3" />
                        {roleConfig.shortLabel}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-on-surface-variant mt-0.5">
                      <span className="truncate flex items-center gap-1">
                        <Mail className="w-3 h-3 flex-shrink-0" />
                        {member.email}
                      </span>
                      {member.created_at && (
                        <>
                          <span>•</span>
                          <span className="hidden md:inline">
                            Joined {new Date(member.created_at).toLocaleDateString()}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Role Assignment Dropdown & Actions */}
                <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
                  {/* Role Selector */}
                  <div className="relative">
                    {isUpdating ? (
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-surface-container bg-surface-container-lowest text-xs text-on-surface-variant">
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                        <span>Updating...</span>
                      </div>
                    ) : (
                      <div className="relative">
                        <select
                          value={member.role}
                          disabled={isSelf}
                          onChange={(e) => handleRoleChange(member, e.target.value)}
                          className={`text-xs font-medium rounded-lg px-3 py-1.5 pr-8 border transition-all cursor-pointer ${
                            isSelf
                              ? "bg-surface-container/50 border-surface-container text-on-surface-variant cursor-not-allowed opacity-80"
                              : "bg-surface-container-lowest border-surface-container text-on-surface hover:border-primary/50 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                          }`}
                          title={isSelf ? "You cannot alter your own Owner role." : "Change member permission role"}
                        >
                          <option value="owner">Owner / Co-Owner</option>
                          <option value="doctor">Doctor</option>
                          <option value="front_desk">Front Desk</option>
                          <option value="read_only">Read Only</option>
                        </select>
                      </div>
                    )}
                  </div>

                  {/* Remove Button */}
                  {isSelf ? (
                    <div
                      className="p-2 text-on-surface-variant/40 cursor-not-allowed"
                      title="You cannot remove yourself"
                    >
                      <Lock className="w-4 h-4" />
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirmMember(member)}
                      className="text-on-surface-variant hover:text-rose-600 p-2 rounded-lg hover:bg-rose-50 border border-transparent hover:border-rose-100 transition-colors"
                      title={`Remove access for ${member.name}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}

          {filteredStaff.length === 0 && !loading && (
            <div className="p-12 text-center space-y-3">
              <Users className="w-10 h-10 text-on-surface-variant/50 mx-auto" />
              <p className="text-sm font-semibold text-on-surface">No team members match your filter</p>
              <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                {searchQuery
                  ? `No members found matching "${searchQuery}". Try a different keyword.`
                  : "No team members found for this role filter."}
              </p>
              {(searchQuery || filterRole !== "all") && (
                <button
                  onClick={() => {
                    setSearchQuery("");
                    setFilterRole("all");
                  }}
                  className="text-xs font-semibold text-primary hover:underline mt-2 inline-block"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Permissions Breakdown Card */}
      <div className="bg-surface-container-lowest border border-surface-container rounded-2xl p-5 shadow-xs">
        <h4 className="text-sm font-bold text-on-surface mb-3 flex items-center gap-2">
          <Shield className="w-4 h-4 text-primary" />
          Role Permission Levels Explained
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {Object.entries(ROLE_CONFIGS).map(([key, config]) => {
            const Icon = config.icon;
            return (
              <div
                key={key}
                className="p-3 rounded-xl border border-surface-container bg-surface-container/30 flex items-start gap-3"
              >
                <div className={`p-2 rounded-lg border flex-shrink-0 ${config.badgeBg}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-on-surface">{config.label}</p>
                  <p className="text-[11px] text-on-surface-variant mt-0.5">{config.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────── */}
      {/* Invite Member Modal Dialog */}
      {/* ───────────────────────────────────────────────────────── */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-lg shadow-xl overflow-hidden animate-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-5 border-b border-surface-container flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-on-surface">Invite New Team Member</h3>
                  <p className="text-xs text-on-surface-variant">Send an invitation with temporary login credentials.</p>
                </div>
              </div>
              <button
                onClick={() => setIsInviteModalOpen(false)}
                className="text-on-surface-variant hover:text-on-surface p-1 rounded-lg hover:bg-surface-container"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleInvite} className="p-6 space-y-4">
              <div>
                <label className="overline mb-1.5 block text-xs font-bold">Full Name *</label>
                <input
                  type="text"
                  required
                  value={inviteName}
                  onChange={e => setInviteName(e.target.value)}
                  className="input-field w-full text-sm"
                  placeholder="e.g. Dr. Sarah Jenkins"
                />
              </div>

              <div>
                <label className="overline mb-1.5 block text-xs font-bold">Email Address *</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  className="input-field w-full text-sm"
                  placeholder="sarah@yourclinic.com"
                />
              </div>

              <div>
                <label className="overline mb-1.5 block text-xs font-bold">Assign Role & Permissions *</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
                  {Object.entries(ROLE_CONFIGS).map(([key, config]) => {
                    const Icon = config.icon;
                    const isSelected = inviteRole === key;
                    return (
                      <button
                        type="button"
                        key={key}
                        onClick={() => setInviteRole(key)}
                        className={`p-3 rounded-xl border text-left flex items-start gap-2.5 transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-surface-container hover:bg-surface-container/30"
                        }`}
                      >
                        <div className={`p-1.5 rounded-md border shrink-0 ${config.badgeBg}`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-on-surface flex items-center justify-between">
                            {config.shortLabel}
                            {isSelected && <Check className="w-3.5 h-3.5 text-primary" />}
                          </p>
                          <p className="text-[10px] text-on-surface-variant line-clamp-2 mt-0.5">
                            {config.description}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Modal Footer Actions */}
              <div className="pt-3 border-t border-surface-container flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  disabled={inviting}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-on-surface-variant hover:bg-surface-container transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviting}
                  className="btn-primary py-2 px-5 text-xs flex items-center gap-2"
                >
                  {inviting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Sending Invitation...</span>
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-3.5 h-3.5" />
                      <span>Send Invitation</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────── */}
      {/* Confirmation Modal for Removing Member */}
      {/* ───────────────────────────────────────────────────────── */}
      {deleteConfirmMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-md shadow-xl p-6 space-y-4 animate-in zoom-in-95 duration-150">
            <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-100">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">Remove Team Member?</h3>
              <p className="text-xs text-on-surface-variant mt-1.5">
                Are you sure you want to revoke workspace access for <strong>{deleteConfirmMember.name}</strong> ({deleteConfirmMember.email})? They will immediately lose access to patient charts and dashboard tools.
              </p>
            </div>
            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirmMember(null)}
                disabled={removingUserId !== null}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-on-surface-variant hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmRemove}
                disabled={removingUserId !== null}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors flex items-center gap-2 shadow-xs"
              >
                {removingUserId ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Removing...</span>
                  </>
                ) : (
                  <span>Yes, Revoke Access</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TeamSettings;

