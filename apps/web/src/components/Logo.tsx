import React from 'react';

/**
 * Logo — 金蝶橙色风格图标
 * 设计：橙色弧形箭头环绕中心，贴近金蝶品牌视觉语言
 * 颜色：#FF6A00 橙色（金蝶品牌色）
 */
const SyncLogo: React.FC<{ size?: number }> = ({ size = 32 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* 上半弧箭头：右上弯向右下 */}
    <path
      d="M16 4 A12 12 0 0 1 28 16"
      stroke="#FF6A00"
      strokeWidth="3"
      strokeLinecap="round"
      fill="none"
    />
    <polyline
      points="24,14 28,16 26,20"
      stroke="#FF6A00"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    {/* 下半弧箭头：左下弯向左上 */}
    <path
      d="M16 28 A12 12 0 0 1 4 16"
      stroke="#FF6A00"
      strokeWidth="3"
      strokeLinecap="round"
      fill="none"
    />
    <polyline
      points="8,18 4,16 6,12"
      stroke="#FF6A00"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    {/* 中心圆点 */}
    <circle cx="16" cy="16" r="2.5" fill="#FF6A00" />
  </svg>
);

export default SyncLogo;
