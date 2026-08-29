// ─────────────────────────────────────────────────────────────────────────────
// useTier - Bytelytic OS Tier System Hook
// ─────────────────────────────────────────────────────────────────────────────
//
// This is the SINGLE SOURCE OF TRUTH for all tier-based UI decisions.
//
// How tiers work:
//   CLINIC_TIER=1 → AI Receptionist ($299-399/mo)   - voice, SMS, bookings, dashboard
//   CLINIC_TIER=2 → Clinic OS ($599/mo)              - Tier 1 + digital intake forms + insurance eligibility
//   CLINIC_TIER=3 → Clinic OS Pro ($899/mo)          - Tier 2 + payments + recall + SOAP notes
//
// How to use:
//   const { canAccess, tier, tierLabel } = useTier();
//   {canAccess(2) && <NavItem to="/intakes" label="Intake Forms" />}
//
// How to set per-clinic:
//   Local dev:  VITE_CLINIC_TIER=1 in dashboard/.env
//   Production: Set VITE_CLINIC_TIER in Vercel environment variables per clinic deployment
//
// ─────────────────────────────────────────────────────────────────────────────

const CLINIC_TIER = parseInt(import.meta.env.VITE_CLINIC_TIER || "1", 10);

// ── Tier metadata ─────────────────────────────────────────────────────────────
const TIER_META = {
  1: {
    label:       "AI Receptionist",
    shortLabel:  "Plan 1",
    price:       "$299–399/mo",
    color:       "#7FCD4D",      // brand green
    description: "24/7 voice AI, appointment booking, SMS reminders, staff dashboard",
    upgradeMsg:  "Upgrade to Clinic OS to unlock this feature.",
    upgradeUrl:  "https://bytelytic.com/upgrade",
  },
  2: {
    label:       "Clinic OS",
    shortLabel:  "Plan 2",
    price:       "$599/mo",
    color:       "#3b82f6",      // blue
    description: "Everything in Plan 1 + digital intake forms + insurance eligibility",
    upgradeMsg:  "Upgrade to Clinic OS Pro to unlock this feature.",
    upgradeUrl:  "https://bytelytic.com/upgrade",
  },
  3: {
    label:       "Clinic OS Pro",
    shortLabel:  "Plan 3",
    price:       "$899/mo",
    color:       "#8b5cf6",      // purple
    description: "Everything in Plan 2 + Stripe payments + patient recall + SOAP notes",
    upgradeMsg:  null,           // already on highest tier
    upgradeUrl:  null,
  },
};

// ── Feature map - which tier is required for each feature ─────────────────────
// Used for canAccessFeature("intake") style checks if needed.
export const FEATURE_TIERS = {
  // Tier 1 - always available
  dashboard:      1,
  appointments:   1,
  patients:       1,
  call_logs:      1,
  analytics:      1,
  settings:       1,
  voice_ai:       1,
  sms:            1,
  booking_widget: 1,

  // Tier 2 - Clinic OS
  intake_forms:   2,
  eligibility:    2,
  insurance:      2,

  // Tier 3 - Clinic OS Pro
  payments:       3,
  recall:         3,
  waitlist:       3,
  soap_notes:     3,
  voice_clone:    3,
};

// ─────────────────────────────────────────────────────────────────────────────
// useTier Hook
// ─────────────────────────────────────────────────────────────────────────────
export function useTier() {
  const tier    = CLINIC_TIER;
  const meta    = TIER_META[tier] || TIER_META[1];

  return {
    // Core tier value (1, 2, or 3)
    tier,

    // canAccess(requiredTier) → true if clinic tier >= required tier
    // Usage: {canAccess(2) && <NavItem to="/intakes" />}
    canAccess: (requiredTier) => tier >= requiredTier,

    // canAccessFeature("intake") → true if feature is unlocked
    // Usage: {canAccessFeature("intake") && <IntakeButton />}
    canAccessFeature: (feature) => {
      const required = FEATURE_TIERS[feature] ?? 1;
      return tier >= required;
    },

    // Tier metadata for display
    tierLabel:   meta.label,
    shortLabel:  meta.shortLabel,
    tierColor:   meta.color,
    tierPrice:   meta.price,
    description: meta.description,

    // Upgrade messaging (null if already on highest tier)
    upgradeMsg:  meta.upgradeMsg,
    upgradeUrl:  meta.upgradeUrl,

    // Convenience booleans
    isPlan1:  tier === 1,
    isPlan2:  tier === 2,
    isPlan3:  tier === 3,
    isAtLeast2: tier >= 2,
    isAtLeast3: tier >= 3,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// TierGate - React component wrapper
// ─────────────────────────────────────────────────────────────────────────────
// Use this to gate any JSX block behind a tier:
//
//   <TierGate requires={2}>
//     <IntakeDashboard />
//   </TierGate>
//
// By default renders nothing if tier insufficient.
// Pass fallback={<UpgradeBanner />} to show something instead.
//
export function TierGate({ requires, children, fallback = null }) {
  const { canAccess } = useTier();
  if (!canAccess(requires)) return fallback;
  return children;
}

// ─────────────────────────────────────────────────────────────────────────────
// UpgradeBadge - inline "Upgrade to Plan X" tag
// ─────────────────────────────────────────────────────────────────────────────
// Use inside sidebar or settings to show a locked badge:
//
//   <UpgradeBadge requiredTier={2} />
//
//
export function UpgradeBadge({ requiredTier, short = false }) {
  const { canAccess } = useTier();
  if (canAccess(requiredTier)) return null;

  const meta = TIER_META[requiredTier] || TIER_META[2];
  return (
    <span
      style={{
        display:       "inline-flex",
        alignItems:    "center",
        gap:           "3px",
        padding:       "1px 7px",
        borderRadius:  "999px",
        fontSize:      "0.6rem",
        fontWeight:    800,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        backgroundColor: `${meta.color}22`,
        color:           meta.color,
        border:          `1px solid ${meta.color}44`,
        flexShrink:      0,
        whiteSpace:      "nowrap",
      }}
    >
      🔒 {short ? `P${requiredTier}` : meta.shortLabel}
    </span>
  );
}
