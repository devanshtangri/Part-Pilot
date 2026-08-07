import type { BuiltInAvatarId } from "../types/auth";

interface UserAvatarProps {
  avatarId: BuiltInAvatarId;
  displayName: string;
  imageUrl?: string | null;
  className?: string;
}

function initials(value: string): string {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "PP";
  const first = words[0]?.[0] ?? "P";
  const last =
    words.length > 1
      ? words[words.length - 1]?.[0] ?? ""
      : words[0]?.[1] ?? "";
  return `${first}${last}`.toUpperCase();
}

function AvatarIcon({ avatarId }: { avatarId: BuiltInAvatarId }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  };

  if (avatarId === "chip") {
    return (
      <svg {...common}>
        <rect x="6" y="6" width="12" height="12" rx="2.5" />
        <circle cx="12" cy="12" r="2.6" />
        <path d="M9 2v4M15 2v4M9 18v4M15 18v4" />
        <path d="M2 9h4M2 15h4M18 9h4M18 15h4" />
      </svg>
    );
  }

  if (avatarId === "circuit") {
    return (
      <svg {...common}>
        <circle cx="5" cy="6" r="1.7" />
        <circle cx="19" cy="7" r="1.7" />
        <circle cx="18" cy="18" r="1.7" />
        <path d="M6.7 6H10v5h5V7h2.3" />
        <path d="M10 11v7h6.3" />
        <path d="M5 14v4h5" />
      </svg>
    );
  }

  if (avatarId === "terminal") {
    return (
      <svg {...common}>
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="m7 9 3 3-3 3M12.5 15H17" />
      </svg>
    );
  }

  if (avatarId === "storage") {
    return (
      <svg {...common}>
        <ellipse cx="12" cy="6" rx="7" ry="3" />
        <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
        <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      </svg>
    );
  }

  if (avatarId === "rocket") {
    return (
      <svg {...common}>
        <path d="M14.5 4.2c2.1-1.2 4.3-1.3 5.3-1-.1 1-.7 3.2-2.2 5.1l-5.8 7.2-4.1-4.1 6.8-7.2Z" />
        <circle cx="15.5" cy="7.4" r="1.6" />
        <path d="m9.1 10-4.2.7-2 3 5.1.1" />
        <path d="m13.1 14 0 5.1-3 2 0.7-4.3" />
        <path d="M6.7 17.3 4 20" />
      </svg>
    );
  }

  return null;
}

// PARTPILOT:USER_AVATAR_COMPONENT:V602
export function UserAvatar({
  avatarId,
  displayName,
  imageUrl = null,
  className = ""
}: UserAvatarProps) {
  return (
    <span
      className={`partpilot-user-avatar is-${avatarId} ${
        imageUrl ? "has-custom-image" : ""
      } ${className}`.trim()}
      data-partpilot-avatar="PARTPILOT:USER_AVATAR_COMPONENT:V602"
      aria-hidden="true"
    >
      {imageUrl ? (
        <img src={imageUrl} alt="" />
      ) : avatarId === "initials" ? (
        <span className="partpilot-user-avatar-initials">
          {initials(displayName)}
        </span>
      ) : (
        <AvatarIcon avatarId={avatarId} />
      )}
    </span>
  );
}
