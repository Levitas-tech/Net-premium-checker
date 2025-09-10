const fs = require('fs');
const path = require('path');

// Files to fix
const files = [
  'frontend/src/components/historical/HistoricalBacktest.js',
  'frontend/src/components/portfolio/PortfolioList.js',
  'frontend/src/components/portfolio/PortfolioView.js',
  'frontend/src/components/trading/OptionLegCard.js',
  'frontend/src/components/trading/OptionLegEditForm.js',
  'frontend/src/components/trading/OptionLegForm.js',
  'frontend/src/components/trading/PnLSummary.js'
];

// Fixes to apply
const fixes = [
  // HistoricalBacktest.js
  {
    file: 'frontend/src/components/historical/HistoricalBacktest.js',
    search: "import { Calendar, Download, Play, Pause, RotateCcw, BarChart3, TrendingUp, TrendingDown, X, Check, AlertCircle, RefreshCw, Eye, EyeOff, ChevronDown, ChevronUp, FileText, Save, Edit, Trash2, Plus, Minus, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Clock, DollarSign, Percent, Target, Zap, Activity, Users, Shield, Settings, Home, Search, Filter, SortAsc, SortDesc, MoreHorizontal, MoreVertical, Copy, Share, ExternalLink, Info, HelpCircle, Star, Heart, ThumbsUp, ThumbsDown, MessageCircle, Mail, Phone, MapPin, Globe, Lock, Unlock, Key, User, UserCheck, UserX, UserPlus, UserMinus, Users, UserCog, UserEdit, UserSearch, UserShield, UserStar, UserHeart, UserThumbsUp, UserThumbsDown, UserMessageCircle, UserMail, UserPhone, UserMapPin, UserGlobe, UserLock, UserUnlock, UserKey } from 'lucide-react';",
    replace: "import { Download, Play, Pause, RotateCcw, BarChart3, TrendingUp, TrendingDown, X, Check, AlertCircle, RefreshCw, Eye, EyeOff, ChevronDown, ChevronUp, FileText, Save, Edit, Trash2, Plus, Minus, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Clock, DollarSign, Percent, Target, Zap, Activity, Users, Shield, Settings, Home, Search, Filter, SortAsc, SortDesc, MoreHorizontal, MoreVertical, Copy, Share, ExternalLink, Info, HelpCircle, Star, Heart, ThumbsUp, ThumbsDown, MessageCircle, Mail, Phone, MapPin, Globe, Lock, Unlock, Key, User, UserCheck, UserX, UserPlus, UserMinus, Users, UserCog, UserEdit, UserSearch, UserShield, UserStar, UserHeart, UserThumbsUp, UserThumbsDown, UserMessageCircle, UserMail, UserPhone, UserMapPin, UserGlobe, UserLock, UserUnlock, UserKey } from 'lucide-react';"
  },
  // PortfolioList.js
  {
    file: 'frontend/src/components/portfolio/PortfolioList.js',
    search: "import { Plus, Edit, Trash2, Eye, BarChart3, TrendingUp, TrendingDown, RefreshCw, AlertCircle, Activity, Users, Shield, Settings, Home, Search, Filter, SortAsc, SortDesc, MoreHorizontal, MoreVertical, Copy, Share, ExternalLink, Info, HelpCircle, Star, Heart, ThumbsUp, ThumbsDown, MessageCircle, Mail, Phone, MapPin, Globe, Lock, Unlock, Key, User, UserCheck, UserX, UserPlus, UserMinus, Users, UserCog, UserEdit, UserSearch, UserShield, UserStar, UserHeart, UserThumbsUp, UserThumbsDown, UserMessageCircle, UserMail, UserPhone, UserMapPin, UserGlobe, UserLock, UserUnlock, UserKey } from 'lucide-react';",
    replace: "import { Plus, Trash2, Eye, BarChart3, TrendingUp, TrendingDown, RefreshCw, AlertCircle, Activity, Users, Shield, Settings, Home, Search, Filter, SortAsc, SortDesc, MoreHorizontal, MoreVertical, Copy, Share, ExternalLink, Info, HelpCircle, Star, Heart, ThumbsUp, ThumbsDown, MessageCircle, Mail, Phone, MapPin, Globe, Lock, Unlock, Key, User, UserCheck, UserX, UserPlus, UserMinus, Users, UserCog, UserEdit, UserSearch, UserShield, UserStar, UserHeart, UserThumbsUp, UserThumbsDown, UserMessageCircle, UserMail, UserPhone, UserMapPin, UserGlobe, UserLock, UserUnlock, UserKey } from 'lucide-react';"
  }
];

// Apply fixes
fixes.forEach(fix => {
  if (fs.existsSync(fix.file)) {
    let content = fs.readFileSync(fix.file, 'utf8');
    content = content.replace(fix.search, fix.replace);
    fs.writeFileSync(fix.file, content);
    console.log(`Fixed ${fix.file}`);
  }
});

console.log('ESLint fixes applied!');
