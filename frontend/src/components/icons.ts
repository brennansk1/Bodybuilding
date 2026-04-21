/**
 * Centralized Lucide icon re-exports.
 *
 * Rule: the rest of the app imports icons *from here only* — not directly
 * from `lucide-react`. That way we:
 *   - keep a single source of truth for which glyphs are allowed,
 *   - ban emoji + Unicode status characters in favor of stroke-consistent SVG,
 *   - can swap icon libraries later without touching 80+ files.
 *
 * If you need a new icon: add it to the export list below, then use it
 * by its exact named export.
 */

export {
  // Structure / layout
  Menu,
  X,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  // Status
  Check,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  // Action
  Plus,
  Minus,
  Edit3,
  Trash2,
  Settings as Cog,
  LogOut,
  RotateCcw,
  Copy,
  ExternalLink,
  // Content domain — training / nutrition / body
  Dumbbell,
  Flame,
  Target,
  Trophy,
  Crown,
  Sparkles,
  Moon,
  Zap,
  Calendar,
  CalendarDays,
  Clock,
  ScaleIcon as Scale,
  Activity,
  TrendingUp,
  TrendingDown,
  LineChart,
  PieChart,
  BarChart3,
  // Photo / media
  Camera,
  ImageIcon as Image,
  // User
  User,
  UserCircle,
  // Utility
  Search,
  Filter,
  Download,
  Upload,
  RefreshCcw,
  Bookmark,
  Eye,
  EyeOff,
  HelpCircle,
  Lock,
  Unlock,
  Bell,
} from "lucide-react";

export type { LucideIcon } from "lucide-react";
