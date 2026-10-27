import React from 'react';

const SyncLogo: React.FC<{ size?: number }> = ({ size = 32 }) => (
  <svg
    aria-hidden="true"
    width={size}
    height={size}
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <rect width="40" height="40" rx="12" fill="#2DD4BF" />
    <path
      d="M12 16.5A9 9 0 0 1 27.8 13L30 15.5M30 15.5V10.5M30 15.5H25"
      stroke="#10363A"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M28 23.5A9 9 0 0 1 12.2 27L10 24.5M10 24.5V29.5M10 24.5H15"
      stroke="#10363A"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export default SyncLogo;
